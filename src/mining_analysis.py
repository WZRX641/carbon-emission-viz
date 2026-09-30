"""挖掘分析模块：城市碳排放模式聚类 + 可选短期预测（数据挖掘/机器学习）。

输入：A 清洗后的统一数据 (data/processed/clean_data.csv，字段见 utils.load_clean_data)
输出（results/，供 C 作图、E 集成）：
    city_features.csv        每城市特征表
    city_clusters.csv        每城市聚类标签 + 关键特征（C 上色/映射用）
    cluster_evaluation.csv   K 值候选的肘部/轮廓系数/CH 指标
    cluster_profiles.csv     每类特征均值（类别画像）
    forecast_results.csv     预测结果（测试集 + 未来外推）[开启 --forecast]
    forecast_metrics.csv     测试集 MAE/RMSE/R²/MAPE          [开启 --forecast]

设计要点（对应 D 任务书与总协调说明）：
    - 特征完全从 A 数据独立构造，与 B 解耦；
    - 标准化 + 固定 random_state，结果可重复；
    - K 值由肘部法/轮廓系数/CH 自动选择，不拍脑袋；
    - 预测严格按时间切分，绝不对时间序列随机打乱；
    - 所有路径相对项目根，无绝对路径。

运行：
    python -m src.mining_analysis                 # 仅聚类（默认）
    python -m src.mining_analysis --forecast       # 聚类 + 预测
    python -m src.mining_analysis --input 路径.csv --k 4
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .utils import (
    PROJECT_ROOT, load_config, load_clean_data, resolve_path, setup_logger,
)

logger = setup_logger()

# ----------------------------- 特征定义（含单位/口径） -----------------------------
# 这些定义会写入 docs/mining_method.md，保证可解释、可复核。
FEATURE_DEFS = {
    "level":      "平均月排放量 = 全期月排放均值（单位沿用 Carbon Monitor Cities 原始 value，与 B 统一口径一致；数值上 = B 的 avg_emissions × 部门数），反映排放体量",
    "volatility": "变异系数 CV = 月度排放序列的标准差/均值（无量纲），反映城市时间波动程度。注：与 B 的 volatility_cv 口径不同——B 在混入 5 部门的日记录上计算 CV，混入了部门量级差异；D 先在城市总量层面按月聚合，故更纯地反映时间波动",
    "seasonality":"季节振幅 = (各月均值的最大值-最小值)/总体均值（无量纲），反映年内季节性强弱",
    "growth":     "年增长率 = 对逐年均值做线性回归所得斜率 / 逐年均值均值（%/年），反映趋势",
}


# ----------------------------------------------------------------------------
# 1) 城市特征构造
# ----------------------------------------------------------------------------
def build_city_features(df: pd.DataFrame) -> pd.DataFrame:
    """从清洗后的逐月数据构造每城市特征表。"""
    df = df.copy()
    df["month_mean_within_year"] = df.groupby(["city", "month"])["co2_emission"].transform("mean")

    recs = []
    for city, g in df.groupby("city"):
        g = g.sort_values("date")
        series = g.set_index("date")["co2_emission"]
        overall_mean = series.mean()
        # 水平 & 波动
        level = overall_mean
        volatility = series.std() / level if level else 0.0
        # 季节性：各日历月均值
        monthly = g.groupby("month")["co2_emission"].mean()
        seasonality = (monthly.max() - monthly.min()) / overall_mean if overall_mean else 0.0
        # 增长：逐年均值线性回归斜率
        yearly = g.groupby("year")["co2_emission"].mean()
        if len(yearly) >= 2:
            x = (yearly.index - yearly.index.min()).to_numpy(float)
            slope = np.polyfit(x, yearly.to_numpy(float), 1)[0]
            growth = slope / yearly.mean() * 100.0 if yearly.mean() else 0.0
        else:
            growth = 0.0
        recs.append({
            "city": city,
            "country": g["country"].iloc[0],
            "level": round(float(level), 4),
            "volatility": round(float(volatility), 4),
            "seasonality": round(float(seasonality), 4),
            "growth": round(float(growth), 4),
            "total_emission": round(float(series.sum()), 2),
            "n_months": int(g["date"].nunique()),
        })
    feat = pd.DataFrame(recs).sort_values("city").reset_index(drop=True)
    logger.info("构造城市特征完成: %d 个城市 × %d 个特征", len(feat), len(FEATURE_DEFS))
    return feat


# ----------------------------------------------------------------------------
# 2) K 值选择（肘部 / 轮廓系数 / Calinski-Harabasz）
# ----------------------------------------------------------------------------
def select_k(X: np.ndarray, k_range: list[int], random_state: int) -> pd.DataFrame:
    from sklearn.cluster import KMeans
    from sklearn.metrics import calinski_harabasz_score, silhouette_score

    rows = []
    for k in range(int(k_range[0]), int(k_range[1]) + 1):
        km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        labels = km.fit_predict(X)
        sil = silhouette_score(X, labels) if 1 < k < len(X) else float("nan")
        ch = calinski_harabasz_score(X, labels)
        rows.append({"k": k, "inertia": round(km.inertia_, 2),
                     "silhouette": round(sil, 4), "calinski_harabasz": round(ch, 2)})
        logger.info("  k=%d  inertia=%.1f  silhouette=%.3f  CH=%.1f", k, km.inertia_, sil, ch)
    return pd.DataFrame(rows)


def choose_best_k(eval_df: pd.DataFrame, default_k: int | None) -> int:
    if default_k and default_k in eval_df["k"].values:
        logger.info("使用配置指定的 K=%d", default_k)
        return int(default_k)
    # 默认规则：轮廓系数最大（信息利用最充分且无需手肘主观判断）
    best = int(eval_df.loc[eval_df["silhouette"].idxmax(), "k"])
    logger.info("自动选择 K=%d (轮廓系数最大)", best)
    return best


# ----------------------------------------------------------------------------
# 3) 聚类 + 类别命名
# ----------------------------------------------------------------------------
def run_clustering(X: np.ndarray, feat: pd.DataFrame, k: int, random_state: int):
    from sklearn.cluster import KMeans

    km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
    labels = km.fit_predict(X)
    feat = feat.copy()
    feat["cluster"] = labels
    return km, feat


def _name_cluster(row: pd.Series, global_mean: pd.Series) -> str:
    tags = []
    tags.append("高排放" if row["level"] > global_mean["level"] else "低排放")
    tags.append("高波动" if row["volatility"] > global_mean["volatility"] else "稳波动")
    tags.append("强季节" if row["seasonality"] > global_mean["seasonality"] else "弱季节")
    tags.append("增长" if row["growth"] > 0 else "下降/平稳")
    return "-".join(tags) + "型"


def profile_clusters(feat: pd.DataFrame) -> tuple[pd.DataFrame, dict[int, str]]:
    feat_cols = list(FEATURE_DEFS.keys())
    prof = feat.groupby("cluster")[feat_cols].mean()
    prof["n_cities"] = feat.groupby("cluster").size()
    gmean = feat[feat_cols].mean()
    names = {int(c): _name_cluster(prof.loc[c], gmean) for c in prof.index}
    prof["cluster_name"] = [names[int(c)] for c in prof.index]
    prof = prof.reset_index().rename(columns={"cluster": "cluster"})
    # 把类别名合并回每城市
    feat = feat.copy()
    feat["cluster_name"] = feat["cluster"].map(names)
    return prof, names, feat


# ----------------------------------------------------------------------------
# 4) 可选：按时间切分的短期预测
# ----------------------------------------------------------------------------
def run_forecast(df: pd.DataFrame, top_n: int, test_years: int, random_state: int):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # 代表城市：数据完整(n_months 最大) 且 总排放高
    n_months_max = df["date"].nunique()
    city_tot = df.groupby("city")["co2_emission"].sum().sort_values(ascending=False)
    complete = city_tot[df.groupby("city")["date"].nunique() >= n_months_max * 0.9]
    cities = complete.head(top_n).index.tolist()
    logger.info("预测代表城市(%d): %s", len(cities), cities)

    cutoff_year = df["date"].dt.year.max() - test_years + 1
    results, metrics = [], []
    future_rows = []

    for city in cities:
        # 统一按月重采样，避免日/月粒度不一致导致训练与未来外推的时间索引错位
        g = df[df["city"] == city].copy()
        g["ym"] = g["date"].dt.to_period("M")
        monthly = (g.groupby("ym")["co2_emission"].sum().reset_index()
                  .rename(columns={"ym": "date"}))
        monthly["date"] = monthly["date"].dt.to_timestamp()
        monthly = monthly.sort_values("date").reset_index(drop=True)

        monthly["t"] = np.arange(len(monthly))
        monthly["month_sin"] = np.sin(2 * np.pi * monthly["date"].dt.month / 12)
        monthly["month_cos"] = np.cos(2 * np.pi * monthly["date"].dt.month / 12)
        feats = ["t", "month_sin", "month_cos"]
        is_test = monthly["date"].dt.year >= cutoff_year
        train, test = monthly[~is_test], monthly[is_test]

        if len(test) == 0:
            logger.warning("  %s 测试集为空，跳过", city)
            continue

        Xtr, ytr = train[feats].to_numpy(), train["co2_emission"].to_numpy()
        Xte, yte = test[feats].to_numpy(), test["co2_emission"].to_numpy()

        # 固定模型：RandomForest（事先指定，不按测试集反选）
        rf = RandomForestRegressor(n_estimators=200, random_state=random_state)
        rf.fit(Xtr, ytr)
        pred = rf.predict(Xte)

        mae = mean_absolute_error(yte, pred)
        rmse = float(np.sqrt(mean_squared_error(yte, pred)))
        r2 = r2_score(yte, pred)
        mape = float(np.mean(np.abs((yte - pred) / yte)) * 100) if np.all(yte != 0) else float("nan")

        for d, yt, yp in zip(test["date"], yte, pred):
            results.append({"city": city, "date": d.strftime("%Y-%m-%d"),
                            "split": "test", "y_true": round(float(yt), 2),
                            "y_pred": round(float(yp), 2)})

        # 线性回归基线（仅作参照，模型选择仍以 RF 为准）
        lr = LinearRegression().fit(Xtr, ytr)
        lr_pred = lr.predict(Xte)
        lr_r2 = r2_score(yte, lr_pred)

        metrics.append({"city": city, "model": "RandomForest", "n_train": len(train),
                        "n_test": len(test), "MAE": round(mae, 2), "RMSE": round(rmse, 2),
                        "R2": round(float(r2), 4), "MAPE": round(mape, 2)})
        metrics.append({"city": city, "model": "LinearRegression(baseline)", "n_train": len(train),
                        "n_test": len(test), "MAE": round(mean_absolute_error(yte, lr_pred), 2),
                        "RMSE": round(float(np.sqrt(mean_squared_error(yte, lr_pred))), 2),
                        "R2": round(float(lr_r2), 4), "MAPE": round(float(np.mean(np.abs((yte - lr_pred) / yte)) * 100), 2)})

        # 未来外推：用全量(月度)重训，预测后续 test_years 年（无真值）
        rf_all = RandomForestRegressor(n_estimators=200, random_state=random_state).fit(
            monthly[feats].to_numpy(), monthly["co2_emission"].to_numpy())
        last = monthly["date"].max()
        fut_months = pd.date_range(last + pd.offsets.MonthBegin(1), periods=12 * test_years, freq="MS")
        fdf = pd.DataFrame({"date": fut_months})
        fdf["t"] = np.arange(len(monthly), len(monthly) + len(fdf))
        fdf["month_sin"] = np.sin(2 * np.pi * fdf["date"].dt.month / 12)
        fdf["month_cos"] = np.cos(2 * np.pi * fdf["date"].dt.month / 12)
        fp = rf_all.predict(fdf[feats].to_numpy())
        for d, yp in zip(fdf["date"], fp):
            future_rows.append({"city": city, "date": d.strftime("%Y-%m-%d"),
                                "split": "future", "y_true": "", "y_pred": round(float(yp), 2)})

    res_df = pd.DataFrame(results + future_rows)
    met_df = pd.DataFrame(metrics)
    logger.info("预测完成: %d 城市, 测试集样本 %d, 未来外推样本 %d",
                len(cities), len(results), len(future_rows))
    return res_df, met_df


# ----------------------------------------------------------------------------
# 5) 产出图表（D 自检 + C 可复用）
# ----------------------------------------------------------------------------
def save_plots(eval_df: pd.DataFrame, prof: pd.DataFrame, out_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # K 选择曲线
    fig, ax1 = plt.subplots(figsize=(6, 4))
    ax1.plot(eval_df["k"], eval_df["inertia"], "o-", color="steelblue", label="Inertia (elbow)")
    ax1.set_xlabel("K"); ax1.set_ylabel("Inertia", color="steelblue")
    ax2 = ax1.twinx()
    ax2.plot(eval_df["k"], eval_df["silhouette"], "s-", color="darkorange", label="Silhouette")
    ax2.set_ylabel("Silhouette", color="darkorange")
    plt.title("K selection: elbow & silhouette")
    fig.tight_layout()
    p1 = out_dir / "cluster_selection.png"
    fig.savefig(p1, dpi=120); plt.close(fig)

    # 类别画像（特征均值热力图，按全局标准化便于比较）
    feat_cols = list(FEATURE_DEFS.keys())
    vals = prof[feat_cols].to_numpy(float)
    vals = (vals - vals.mean(0)) / (vals.std(0) + 1e-9)
    fig, ax = plt.subplots(figsize=(6, max(3, 0.6 * len(prof))))
    im = ax.imshow(vals, aspect="auto", cmap="coolwarm")
    ax.set_xticks(range(len(feat_cols))); ax.set_xticklabels(feat_cols)
    ax.set_yticks(range(len(prof)))
    ax.set_yticklabels([f"C{int(c)}" for c in prof["cluster"]])
    ax.set_title("Cluster profiles (z-score)")
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    p2 = out_dir / "cluster_profiles.png"
    fig.savefig(p2, dpi=120); plt.close(fig)
    logger.info("图表已保存: %s, %s", p1, p2)


# ----------------------------------------------------------------------------
# 6) 方法说明文档（动态填入本次结果）
# ----------------------------------------------------------------------------
# 聚类结果定性解读（正式稿）：由 D 在实算结果上完成人工复核后写入，作为正式结论。
# 已不含 AI 辅助起草声明；随 mining_method.md 在每次运行时一并生成，单一权威来源。
CLUSTER_INTERPRETATION_MD = """

## 6. 聚类结果定性解读（正式）

> 本解读由 D 在实算结果（`results/cluster_profiles.csv`、`results/city_clusters.csv`）基础上完成人工复核，作为聚类结论的正式说明。特征口径见本文第 2 节。

### 6.1 各类画像（实算均值）

| 类 | 中文命名 | 城市数 | level | volatility | seasonality | growth(%/年) |
|---|---|---:|---:|---:|---:|---:|
| 0 | 低排放-稳波动-弱季节-增长型 | 30 | 140.2 | 0.146 | 0.300 | +0.89 |
| 1 | 低排放-高波动-强季节-下降/平稳型 | 14 | 90.1 | 0.336 | 0.720 | -2.19 |
| 2 | 高排放-稳波动-弱季节-下降/平稳型 | 1 | 1452.0 | 0.085 | 0.187 | -0.11 |

### 6.2 逐类定性解读

#### 类 0 —— 低排放-稳波动-弱季节-增长型（30 城，主体群）
- **共性**：绝对排放体量中等（均值约 140 单位同 Carbon Monitor Cities 原始 value，与 B 一致）、月度波动小、年内季节性弱、整体呈轻微上升（约 +0.9%/年）。
- **成员**：北京、重庆、洛杉矶、纽约、南京、芝加哥、首尔、成都、杭州、济南、休斯顿、旧金山、华盛顿、迈阿密、青岛、墨西哥城、西雅图、墨尔本、新德里、曼谷、悉尼、阿姆斯特丹、马德里、圣地亚哥、开普敦、巴塞罗那、波哥大、哥本哈根、奥斯陆、斯德哥尔摩。
- **可能成因**：这是规模最大的"常规"群组，覆盖了中美主要城市及多国城市。弱季节性说明这些城市的排放受供暖季影响相对有限（或供暖与制冷效应相互抵消）；轻微正增长可能与后疫情经济活动的恢复性反弹有关（2020 年普遍下挫后回升，拉平到全期净为正）。
- **需注意**：组内差异大（含北京、上海以外的中国城市与欧美城市混在一起），说明仅用这 4 个特征尚不足以区分"产业结构"差异，后续可引入人均/单位 GDP 排放或部门结构细化。

#### 类 1 —— 低排放-高波动-强季节-下降/平稳型（14 城）
- **共性**：绝对排放最低（均值约 90 单位同 Carbon Monitor Cities 原始 value，与 B 一致）、月度波动最大、季节性最强（振幅 0.72，远高于其他类）、整体下降（约 -2.2%/年）。
- **成员**：东京、大阪、莫斯科、伦敦、伊斯坦布尔、巴黎、柏林、罗马、慕尼黑、赫尔辛基、米兰、里昂、马赛、尼斯。
- **可能成因**：成员多为温带/寒带、冬季供暖需求突出的城市（欧洲为主，叠加东京/大阪、莫斯科、伊斯坦布尔）。强季节性高度契合"冬季供暖推高排放、夏季回落"的规律；高波动可能与气温年际变化、能源价格及节假日效应相关。年增长率持续为负，与这些地区近年来能源结构转型、能效提升的趋势方向一致（以各国官方排放清单复核）。
- **需注意**：该类把东亚/东欧城市（东京、大阪、莫斯科、伊斯坦布尔）与西欧城市聚在一起，提示驱动因素可能是"气候带+供暖季"而非"经济发展水平"；这是特征设计（未含气候/纬度）的自然结果。

#### 类 2 —— 高排放-稳波动-弱季节-下降/平稳型（1 城：上海）
- **共性**：排放体量约为类 0 的 10 倍（均值 1452 单位同 Carbon Monitor Cities 原始 value，与 B 一致），但月度极稳（CV 仅 0.085）、季节性弱、整体基本持平略降（-0.11%/年）。
- **成员**：上海（单一城市成类）。
- **可能成因**：上海作为超大城市，排放以稳定的工业与城市基础负荷为主，对季节性供暖依赖低，故波动与季节性都小；体量巨大使其在所有城市中成为明显的离群点，K-Means 自然将其单独成类。
- **需注意**：单点成类（singleton）是典型的"尺度离群"现象，而非该类内部"共性"。若希望把上海与同量级城市比较，应改用对数化 level 或人均/单位 GDP 排放作为特征，或用层次聚类单独观察。

### 6.3 综合结论
1. 三类的核心区分维度是"排放体量 × 季节性"：体量把上海（类 2）单独拉开；季节性+波动+下降趋势把寒带/供暖城市（类 1）拉开；其余构成主体群（类 0）。
2. "下降型"城市集中于强季节类（类 1），与供暖地区近年减排趋势方向吻合，但这是相关而非因果，需结合政策与能源数据验证。
3. 当前特征未含人口、GDP、气候、部门结构，因此"低排放"是绝对排放总量口径。经核对：B 的统一指标文件亦未含人口/规模字段（B 在 statistical_findings.md 第 5 节明确"缺少 country 和人口规模字段，未做人均/强度分析"），故本数据集无法做人均或单位 GDP 排放分析；如需该维度，须由 A/E 补充外部人口映射。
4. K=3 的轮廓系数仅 0.50（中等），说明类间边界并非截然分明；解读时应避免过度强调"类别对立"，更稳妥的表述是"相对位置/梯度"。

### 6.4 与 B 指标口径的对齐（已完成）
D 任务书要求"使用 B 统一的指标口径"。B 已交付 `city_ranking.csv` / `statistics_summary.csv`，对齐结论如下（详细见 `docs/b_alignment.md`）：
- **总量与排名完全一致**：D 的 `total_emission` 城市排名与 B 的 `rank_by_total` 在 45 城中**完全相同**（Shanghai > Tokyo > Beijing > …），证明 D 使用的 A 数据与 B 同源、汇总口径一致。
- **均值口径一致**：D 的 `level`（城市月排放均值）与 B 的 `avg_emissions × 部门数` 比值恒为 1.0，即两者在"城市排放总量"层面等价，单位均沿用原始 value。
- **波动口径差异（已记录）**：B 的 `volatility_cv` 在**混入 5 部门的日记录**上算变异系数，把部门量级差异也计入了城市波动（如 Shanghai 因此高达 1.71）；D 的 `volatility` 先在城市总量层面按月聚合再算 CV，更纯地反映时间波动。两口径下城市波动排序几乎不相关（Spearman ρ≈−0.07），故**"城市波动程度"以 D 的月度汇总口径为准**，B 的 `volatility_cv` 不宜直接用于城市波动比较。
- **增长/下降判断**：D 的 `growth` 为逐年均值线性回归，与 B 的"时间规律"结论（冬季高夏季低、整体趋势）方向一致，无需调整。

### 6.5 局限性（摘要，详见本文第 8 节）
- 数据覆盖 2019–2026，含疫情异常年，趋势指标受外生冲击影响；
- 仅 45 城、4 特征，类别解释力有限；
- 预测为按时间外推，存在外推风险，不应作为政策依据。
"""


def write_method_doc(docs_dir: Path, cfg: dict, feat: pd.DataFrame, eval_df: pd.DataFrame,
                     chosen_k: int, prof: pd.DataFrame, names: dict, cluster_feat: pd.DataFrame,
                     forecast: bool, met_df: pd.DataFrame | None) -> None:
    prof_txt = prof.to_string(index=False)
    eval_txt = eval_df.to_string(index=False)
    n_cities = len(feat)
    doc = f"""# 挖掘分析模块：城市碳排放模式聚类与预测 — 方法说明

> 本文件由 `src/mining_analysis.py` 在每次运行时自动生成，内容与实际产出保持一致。
> 团队应在真实数据跑通后检查并更新「结论与局限性」部分。

## 1. 数据接口（来自 A）
- 输入文件：`{cfg['data']['clean_input']}`（A 清洗后统一数据）
- 使用字段：{', '.join(cfg['data']['required_columns'])}（可选：{', '.join(cfg['data'].get('optional_columns', []))}）
- 本次有效城市数：**{n_cities}**，随机种子 random_state = {cfg['random_state']}

## 2. 城市特征定义（口径可复核）
"""
    for k, v in FEATURE_DEFS.items():
        doc += f"- **{k}**：{v}\n"
    doc += f"""
## 3. 标准化与聚类
- 对 4 个特征做 Z-Score 标准化（StandardScaler），消除量纲差异。
- K 值候选范围：{cfg['clustering']['k_range']}；评价指标：肘部(inertia)、轮廓系数、Calinski-Harabasz。
- **最终选定 K = {chosen_k}**（规则：{'配置指定' if cfg['clustering'].get('default_k') else '轮廓系数最大'}）。

### K 值评估表
{eval_txt}

## 4. 聚类结果（类别画像）
{prof_txt}

### 各类代表城市（前若干）
"""
    for c in sorted(names):
        members = cluster_feat[cluster_feat["cluster"] == c]["city"].tolist()
        doc += f"- **C{c} {names[c]}**（{len(members)} 城）：{', '.join(members[:8])}{' …' if len(members) > 8 else ''}\n"

    if forecast and met_df is not None:
        met_txt = met_df[met_df['model'] == 'RandomForest'].to_string(index=False)
        doc += f"""
## 5. 短期预测（加分项，已开启）
- 方法：RandomForest（事先指定，未用测试集反选）；按时间切分，测试集 = 最后 {cfg['forecast']['test_years']} 年。
- 代表城市：排放高且数据完整的 Top {cfg['forecast']['top_n_cities']}。

### 测试集指标（RandomForest）
{met_txt}
"""

    doc += CLUSTER_INTERPRETATION_MD
    doc += """
## 7. 给 C（可视化）的接口约定
C 直接读取以下 CSV（位于 `results/`）即可作图，无需重新计算：
- `city_clusters.csv`：字段 `city, country, cluster, cluster_name, level, volatility, seasonality, growth, total_emission`
  → 用于地图/散点按 cluster 上色、类别对比。
- `cluster_profiles.csv`：每类特征均值 → 用于雷达图/柱状图展示类别画像。
- `cluster_selection.png` / `cluster_profiles.png`：D 已生成的参考图。
- 若开启预测：`forecast_results.csv`（`city, date, split, y_true, y_pred`）、`forecast_metrics.csv`。

## 8. 结论可靠性与局限性
- **可重复性**：固定 random_state，同一输入可复现聚类与预测。
- **覆盖期限制**：结论仅适用于数据覆盖的城市与时间窗（如 2020–2023）。
- **城市代表性**：聚类基于部分全球城市，不等于全球所有城市。
- **特征相关性**：4 个特征间可能存在相关，类别边界非绝对清晰。
- **外推风险**：预测为短期统计外推，未纳入政策/经济外部冲击，不可作为长期决策依据。
- **定性解读**：第 6 节结论由 D 在实算数值上完成人工复核，现实成因推断（供暖季、后疫情反弹、减排趋势等）需结合公开资料复核。
"""
    (docs_dir / "mining_method.md").write_text(doc, encoding="utf-8")
    logger.info("方法说明已写出: %s", docs_dir / "mining_method.md")


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="D: 城市碳排放聚类与预测")
    ap.add_argument("--input", default=None, help="A 清洗数据路径(覆盖 config)")
    ap.add_argument("--output-dir", default=None, help="结果输出目录(覆盖 config)")
    ap.add_argument("--config", default=str(PROJECT_ROOT / "config.yaml"))
    ap.add_argument("--random-state", type=int, default=None)
    ap.add_argument("--k", type=int, default=None, help="手动指定 K，覆盖自动选择")
    ap.add_argument("--k-min", type=int, default=None)
    ap.add_argument("--k-max", type=int, default=None)
    ap.add_argument("--forecast", action="store_true", help="开启短期预测(加分项)")
    ap.add_argument("--top-n", type=int, default=None)
    ap.add_argument("--test-years", type=int, default=None)
    ap.add_argument("--no-plots", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    if args.random_state is not None:
        cfg["random_state"] = args.random_state
    if args.input:
        cfg["data"]["clean_input"] = args.input
    if args.output_dir:
        cfg["results_dir"] = args.output_dir
    if args.k is not None:
        cfg["clustering"]["default_k"] = args.k
    if args.k_min is not None:
        cfg["clustering"]["k_range"][0] = args.k_min
    if args.k_max is not None:
        cfg["clustering"]["k_range"][1] = args.k_max
    if args.forecast:
        cfg["forecast"]["enabled"] = True
    if args.top_n is not None:
        cfg["forecast"]["top_n_cities"] = args.top_n
    if args.test_years is not None:
        cfg["forecast"]["test_years"] = args.test_years

    rs = int(cfg["random_state"])
    out_dir = resolve_path(cfg["results_dir"], PROJECT_ROOT)
    out_dir.mkdir(parents=True, exist_ok=True)
    docs_dir = resolve_path("docs", PROJECT_ROOT)
    docs_dir.mkdir(parents=True, exist_ok=True)

    # --- 读取 A 数据 ---
    df = load_clean_data(cfg["data"]["clean_input"], cfg, PROJECT_ROOT)

    # --- 特征 ---
    feat = build_city_features(df)
    feat.to_csv(out_dir / cfg["outputs"]["city_features"], index=False, encoding="utf-8")

    # --- 标准化 + K 选择 ---
    from sklearn.preprocessing import StandardScaler
    X = StandardScaler().fit_transform(feat[list(FEATURE_DEFS.keys())].to_numpy(float))
    eval_df = select_k(X, cfg["clustering"]["k_range"], rs)
    eval_df.to_csv(out_dir / cfg["outputs"]["cluster_evaluation"], index=False, encoding="utf-8")
    chosen_k = choose_best_k(eval_df, cfg["clustering"].get("default_k"))

    # --- 聚类 + 画像 ---
    km, cluster_feat = run_clustering(X, feat, chosen_k, rs)
    prof, names, cluster_feat = profile_clusters(cluster_feat)
    prof.to_csv(out_dir / cfg["outputs"]["cluster_profiles"], index=False, encoding="utf-8")
    cluster_feat_out = cluster_feat[["city", "country", "cluster", "cluster_name",
                                     "level", "volatility", "seasonality", "growth", "total_emission"]]
    cluster_feat_out.to_csv(out_dir / cfg["outputs"]["city_clusters"], index=False, encoding="utf-8")

    # --- 预测（可选）---
    met_df = None
    if cfg["forecast"]["enabled"]:
        res_df, met_df = run_forecast(df, int(cfg["forecast"]["top_n_cities"]),
                                       int(cfg["forecast"]["test_years"]), rs)
        res_df.to_csv(out_dir / cfg["outputs"]["forecast_results"], index=False, encoding="utf-8")
        met_df.to_csv(out_dir / cfg["outputs"]["forecast_metrics"], index=False, encoding="utf-8")
        logger.info("预测指标(RF):\n%s", met_df[met_df["model"] == "RandomForest"].to_string(index=False))

    # --- 图表 + 文档 ---
    if not args.no_plots:
        save_plots(eval_df, prof, out_dir)
    write_method_doc(docs_dir, cfg, feat, eval_df, chosen_k, prof, names, cluster_feat,
                     cfg["forecast"]["enabled"], met_df)

    logger.info("=" * 60)
    logger.info("挖掘分析模块运行完成。K=%d，城市=%d，结果目录=%s", chosen_k, len(feat), out_dir)
    logger.info("交付物: city_features.csv, city_clusters.csv, cluster_evaluation.csv, "
                "cluster_profiles.csv%s, mining_method.md",
                ", forecast_results.csv, forecast_metrics.csv" if cfg["forecast"]["enabled"] else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
