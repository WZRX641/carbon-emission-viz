"""统计分析模块：基础统计分析（时间规律、城市排名、部门结构、总览汇总）。

E 集成说明（2026-09-04）：
  - 统计逻辑与 B 原交付完全一致，仅做工程化改造：
    1) 去掉写死的相对路径（原脚本要求在 src/ 目录下运行），改为
       参数化输入/输出路径，可在项目根目录直接运行；
    2) 包一层 main() / CLI，供 run_pipeline.py 一键调用；
    3) 输出文件名与原交付完全一致，保证可视化页面零改动接入。

用法（项目根目录）：
    python -m src.statistics_analysis --input data/raw --output results --docs docs

输出（results/，文件名与 B 交付包一致）：
    time_trend.csv, city_ranking.csv, monthly_pattern.csv, weekend_pattern.csv,
    season_pattern.csv, sector_structure.csv, sector_yearly_trend.csv,
    statistics_summary.csv
输出（docs/）：grouping_note.txt（分组缺失说明）
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# 与数据清洗一致的核心字段
CORE = ["city", "date", "sector", "value"]


def load_and_prepare(input_path: str | Path) -> pd.DataFrame:
    """读取原始数据并做与数据清洗一致的基础校验（字段检查、空值处理）。"""
    path = Path(input_path)
    files = [path] if path.is_file() else sorted(path.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"输入路径下没有 CSV 文件: {path}")
    frames = []
    for p in files:
        df = pd.read_csv(p)
        missing = [c for c in CORE if c not in df.columns]
        if missing:
            raise ValueError(f"{p} 缺少必需列: {missing}")
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)

    # 删除表格软件产生的空白列（如 Unnamed: 4）
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=CORE).copy()

    print(f"数据加载成功！总记录数：{len(df)}")
    print(f"城市数量：{df['city'].nunique()}，部门数量：{df['sector'].nunique()}")
    print(f"日期范围：{df['date'].min()} 至 {df['date'].max()}")

    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day_of_week"] = df["date"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"].apply(lambda x: 1 if x >= 5 else 0)

    def get_season(m):
        if m in [3, 4, 5]:
            return "Spring"
        elif m in [6, 7, 8]:
            return "Summer"
        elif m in [9, 10, 11]:
            return "Autumn"
        else:
            return "Winter"

    df["season"] = df["month"].apply(get_season)
    return df


def coefficient_of_variation(x):
    return x.std() / x.mean() if x.mean() != 0 else np.nan


def run(input_path: str | Path, output_dir: str | Path, docs_dir: str | Path) -> None:
    """执行全部统计分析并写出结果 CSV。"""
    output_dir = Path(output_dir)
    docs_dir = Path(docs_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    df = load_and_prepare(input_path)

    # ---- 1. 月度时间趋势 ----
    df["year_month"] = df["date"].dt.to_period("M")
    monthly_trend = df.groupby("year_month")["value"].sum().reset_index()
    monthly_trend["year_month"] = monthly_trend["year_month"].astype(str)
    monthly_trend.columns = ["year_month", "total_emissions"]
    monthly_trend.to_csv(output_dir / "time_trend.csv", index=False)
    print("已生成时间趋势：results/time_trend.csv (月度粒度)")

    # ---- 2. 城市排名 ----
    city_stats = df.groupby("city")["value"].agg(
        total_emissions="sum",
        avg_emissions="mean",
        peak_emissions="max",
        volatility_cv=coefficient_of_variation,
    ).reset_index()
    city_stats["rank_by_total"] = city_stats["total_emissions"].rank(ascending=False, method="min").astype(int)
    city_stats = city_stats.sort_values("total_emissions", ascending=False)
    city_stats.to_csv(output_dir / "city_ranking.csv", index=False)
    print("已生成城市排名：results/city_ranking.csv")

    # ---- 3. 时间规律：月份 / 周末 / 季节 ----
    monthly_pattern = df.groupby("month")["value"].mean().reset_index()
    monthly_pattern.columns = ["month", "avg_daily_emissions"]
    monthly_pattern.to_csv(output_dir / "monthly_pattern.csv", index=False)

    weekend_pattern = df.groupby("is_weekend")["value"].mean().reset_index()
    weekend_pattern["day_type"] = weekend_pattern["is_weekend"].map({0: "Weekday", 1: "Weekend"})
    weekend_pattern.to_csv(output_dir / "weekend_pattern.csv", index=False)

    season_pattern = df.groupby("season")["value"].mean().reset_index()
    season_pattern.to_csv(output_dir / "season_pattern.csv", index=False)
    print("已生成时间规律：月份、周末、季节")

    # ---- 4. 部门结构 ----
    sector_total = df.groupby("sector")["value"].sum().reset_index()
    sector_total.columns = ["sector", "total_emissions"]
    sector_total["percentage"] = (sector_total["total_emissions"] / sector_total["total_emissions"].sum()) * 100
    sector_total.to_csv(output_dir / "sector_structure.csv", index=False)

    sector_yearly = df.groupby(["year", "sector"])["value"].sum().reset_index()
    sector_yearly.to_csv(output_dir / "sector_yearly_trend.csv", index=False)
    print("已生成行业结构及年度变化")

    # ---- 5. 分组缺失说明 ----
    with open(docs_dir / "grouping_note.txt", "w", encoding="utf-8") as f:
        f.write("注意：原始数据缺少'国家'和'人口规模'字段。根据任务书'没有字段不得虚构'原则，\n")
        f.write("本分析跳过'国家/洲际'和'城市规模'分组对比。如有需要，请数据清洗补充外部映射表。\n")
    print("已生成分组缺失说明：docs/grouping_note.txt")

    # ---- 6. 总览汇总 ----
    summary_data = {
        "metric": [
            "总记录数", "总排放量", "覆盖城市数", "覆盖部门数",
            "日均排放均值", "排放峰值日期", "峰值排放量",
            "最高排放城市", "最高排放部门",
        ],
        "value": [
            len(df),
            df["value"].sum(),
            df["city"].nunique(),
            df["sector"].nunique(),
            df["value"].mean(),
            df.loc[df["value"].idxmax(), "date"].strftime("%Y-%m-%d"),
            df["value"].max(),
            df.groupby("city")["value"].sum().idxmax(),
            df.groupby("sector")["value"].sum().idxmax(),
        ],
    }
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(output_dir / "statistics_summary.csv", index=False)
    print("已生成总览汇总：results/statistics_summary.csv")
    print("\n所有统计分析已完成！请查看 results 文件夹。")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B: 基础统计分析")
    parser.add_argument("--input", required=True, help="原始 CSV 文件或目录")
    parser.add_argument("--output", default="results", help="统计结果输出目录")
    parser.add_argument("--docs", default="docs", help="说明文档输出目录")
    args = parser.parse_args(argv)
    run(args.input, args.output, args.docs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
