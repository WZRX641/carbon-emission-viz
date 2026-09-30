"""挖掘分析模块公共工具：配置加载、日志、数据清洗输出的接口校验与读取。

本文件定义了 D 与 A 之间的「数据接口契约」。只要 A 的清洗结果满足
required_columns 字段口径，D 的 mining_analysis.py 即可直接读取，无需改代码。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

logger = logging.getLogger("D.mining")

# 项目根目录 = src/ 的上一级（E 统一后的项目根）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 城市→国家 权威映射。
# 优先级：项目内 data/city_country_map.csv（A 提供的官方映射表，最权威；
#   E 集成时统一放在 data/ 根，另兼容 D 原来的 data/processed/ 位置）
#   > 内置硬编码兜底（与 A 交付包逐城核对一致，仅用于该文件缺失时的保险）。
# 若 A 的输入已自带 country 列，canonicalize_raw 会优先采用 A 的值，本表只作空白回退。
_MAP_PATHS = [
    PROJECT_ROOT / "data" / "city_country_map.csv",
    PROJECT_ROOT / "data" / "processed" / "city_country_map.csv",
]
_MAP_PATH = next((p for p in _MAP_PATHS if p.exists()), _MAP_PATHS[0])

# 内置兜底（与 A 官方映射表逐城核对一致；2026-09-03 验证 0 差异）
_COUNTRY_OF_CITY_FALLBACK: dict[str, str] = {
    "Amsterdam": "Netherlands", "Bangkok": "Thailand", "Barcelona": "Spain",
    "Beijing": "China", "Berlin": "Germany", "Bogota": "Colombia",
    "Cape Town": "South Africa", "Chengdu": "China", "Chicago": "United States",
    "Chongqing": "China", "Copenhagen": "Denmark", "Hangzhou": "China",
    "Helsinki": "Finland", "Houston": "United States", "Istanbul": "Turkey",
    "Jinan": "China", "London": "United Kingdom", "Los Angeles": "United States",
    "Lyon": "France", "Madrid": "Spain", "Marseille": "France",
    "Melbourne": "Australia", "Mexico City": "Mexico", "Miami": "United States",
    "Milan": "Italy", "Moscow": "Russia", "Munich": "Germany",
    "Nanjing": "China", "New Delhi": "India", "New York": "United States",
    "Nice": "France", "Osaka": "Japan", "Oslo": "Norway", "Paris": "France",
    "Qingdao": "China", "Rome": "Italy", "San Francisco": "United States",
    "Santiago": "Chile", "Seattle": "United States", "Seoul": "South Korea",
    "Shanghai": "China", "Stockholm": "Sweden", "Sydney": "Australia",
    "Tokyo": "Japan", "Washington": "United States",
}


def _load_country_map() -> dict[str, str]:
    """优先从项目内官方映射文件加载，缺失时回退内置表。"""
    if _MAP_PATH.exists():
        try:
            m = pd.read_csv(_MAP_PATH)
            m["city"] = m["city"].astype(str).str.strip()
            m["country"] = m["country"].astype(str).str.strip()
            loaded = dict(zip(m["city"], m["country"]))
            if loaded:
                logger.info("已从官方映射文件加载 city→country: %s (%d 城)",
                            _MAP_PATH.relative_to(PROJECT_ROOT), len(loaded))
                return loaded
        except Exception as e:  # noqa: BLE001
            logger.warning("读取官方映射文件失败，回退内置表: %s", e)
    return dict(_COUNTRY_OF_CITY_FALLBACK)


COUNTRY_OF_CITY: dict[str, str] = _load_country_map()

# 默认配置（与 config.yaml 保持一致，作为兜底）
DEFAULT_CONFIG: dict[str, Any] = {
    "data": {
        "clean_input": "data/processed/clean_data.csv",
        "required_columns": ["city", "country", "date", "year", "month", "co2_emission"],
        "optional_columns": ["sector"],
    },
    "results_dir": "results",
    "random_state": 42,
    "clustering": {"k_range": [2, 10], "default_k": None},
    "forecast": {"enabled": False, "top_n_cities": 5, "test_years": 1},
}


def setup_logger(level: int = logging.INFO) -> logging.Logger:
    if not logger.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s",
                                         datefmt="%H:%M:%S"))
        logger.addHandler(h)
    logger.setLevel(level)
    return logger


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """加载 config.yaml；若文件不存在则返回默认配置。"""
    cfg = DEFAULT_CONFIG
    if path is None:
        path = PROJECT_ROOT / "config.yaml"
    p = Path(path)
    if p.exists():
        with p.open("r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        cfg = _deep_merge(DEFAULT_CONFIG, user_cfg)
        logger.info("已加载配置: %s", p)
    else:
        logger.warning("未找到 config.yaml，使用内置默认配置")
    return cfg


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def resolve_path(p: str | Path, base: Path | None = None) -> Path:
    """把配置里的相对路径解析为相对项目根目录的绝对路径。"""
    p = Path(p)
    if p.is_absolute():
        return p
    return (base or PROJECT_ROOT) / p


def canonicalize_raw(df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """把任意「接近 A 契约」的原始清洗表规范为 D 的统一定义。

    处理 A 实际交付与 D 契约的三类差异：
      1) 排放值列名可能是 `value` -> 映射为 `co2_emission`；
      2) 若按 城市×部门 多行（每日每部门一行），按城市汇总成总量；
      3) 若缺 `country`，用内置 city→country 参考映射补齐（并告警，提示 A/E 确认）。
    返回列：city, country, date, year, month, co2_emission[, sector]。
    """
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]

    # 1) 排放值列
    if "co2_emission" not in df.columns and "value" in df.columns:
        df = df.rename(columns={"value": "co2_emission"})
        logger.warning("排放值列名为 `value`，已映射为 `co2_emission`")
    core = ["city", "date", "year", "month"]
    missing_core = [c for c in core if c not in df.columns]
    if missing_core:
        raise ValueError(f"A 数据缺少必需列: {missing_core}；实际列: {list(df.columns)}")
    if "co2_emission" not in df.columns:
        raise ValueError("缺少排放值列（需 co2_emission 或 value）")

    # 类型规整
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["month"] = pd.to_numeric(df["month"], errors="coerce").astype("Int64")
    df["co2_emission"] = pd.to_numeric(df["co2_emission"], errors="coerce")
    df["city"] = df["city"].astype(str).str.strip()

    # 2) 部门粒度 -> 城市总量（保留 country 等维度列，避免聚合时丢失）
    if "sector" in df.columns:
        per = df.groupby(["city", "date"]).size().max()
        if per and per > 1:
            logger.warning("检测到 sector 粒度(每城市每天 %d 行)，按城市汇总各部门排放为总量", per)
            grp_keys = ["city", "date", "year", "month"]
            if "country" in df.columns:
                grp_keys = ["city", "country", "date", "year", "month"]
            df = (df.groupby(grp_keys, as_index=False)["co2_emission"].sum())

    # 3) country：优先采用 A 提供的列；空白/缺失行才用官方映射回退
    if "country" in df.columns:
        df["country"] = df["country"].astype(str).str.strip()
        missing_mask = df["country"].isin(["", "nan", "None"]) | df["country"].isna()
        n_missing = int(missing_mask.sum())
        if n_missing:
            filled = df.loc[missing_mask, "city"].map(COUNTRY_OF_CITY)
            df.loc[missing_mask, "country"] = filled
            still = int((df["country"].isin(["", "nan"]) | df["country"].isna()).sum())
            if still:
                logger.warning("有 %d 行城市在 A 提供值与映射表中均无法解析 country，留空（请核查）", still)
            logger.info("已采用 A 提供的 country 列，其中 %d 行用官方映射补齐空白", n_missing)
    else:
        logger.warning("A 数据缺 `country` 列，使用官方 city→country 映射补齐（请 A/E 确认口径）")
        df["country"] = df["city"].map(COUNTRY_OF_CITY).fillna("")

    df = df.dropna(subset=["city", "co2_emission", "date"])
    keep = [c for c in ["city", "country", "date", "year", "month", "co2_emission", "sector"] if c in df.columns]
    df = df[keep].sort_values(["city", "date"]).reset_index(drop=True)
    return df


def load_clean_data(input_path: str | Path,
                    config: dict[str, Any],
                    base: Path | None = None) -> pd.DataFrame:
    """读取 A 的清洗后数据，并规范为 D 的统一定义。

    返回列：city, country, date(解析为 datetime), year, month, co2_emission[, sector]。
    路径不存在或内容为空会抛错，提示团队先运行 A 的 data_cleaning 或适配器。
    """
    base = base or PROJECT_ROOT
    path = resolve_path(input_path, base)

    if not path.exists():
        raise FileNotFoundError(
            f"未找到 A 的清洗数据: {path}\n"
            f"请先运行数据清洗的 data_cleaning.py，或用 --input 指定正确路径；\n"
            f"若使用 A 交付包，先运行 `python -m src.ingest_a` 将其转为项目内 clean_data.csv；\n"
            f"框架验证阶段可运行 `python -m src.sample_data` 生成合成样例数据。"
        )

    logger.info("读取清洗数据: %s", path)
    raw = pd.read_csv(path)
    before = len(raw)
    df = canonicalize_raw(raw, config)

    logger.info("数据校验通过: 原始 %d 行 -> 规范后 %d 行, 城市数 %d, 国家数 %d(去空后), 时间范围 %s~%s",
                before, len(df), df["city"].nunique(),
                df.loc[df["country"] != "", "country"].nunique(),
                df["date"].min().date(), df["date"].max().date())
    if len(df) == 0:
        raise ValueError("有效行为 0，请检查 A 的清洗数据内容。")
    return df
