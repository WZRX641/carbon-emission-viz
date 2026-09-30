"""A → D 对接桥：把 A 的交付包转换为 D 框架的统一输入。

为什么需要：A 的实际交付与 D 契约可能有差异，本脚本一次性把它们规范成
`data/processed/clean_data.csv`（D 的 canonical 输入）：
  - 排放值列 `value` → `co2_emission`
  - 部门粒度(城市×部门×日期) → 按城市汇总成总量
  - country：优先采用 A 提供的列；若 A 交付缺 country，则用项目内官方
    映射表(data/processed/city_country_map.csv, 来自 A 的《城市-国家映射表》)
    回退补齐。

用法：
    python -m src.ingest_a                      # 默认读 data/carbonmonitor_clean.csv（E 统一管线产出）
    python -m src.ingest_a --input 路径.csv --output data/processed/clean_data.csv

跑完后再执行：
    python -m src.mining_analysis [--forecast]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .utils import PROJECT_ROOT, canonicalize_raw, resolve_path, setup_logger

logger = setup_logger()

# 集成与测试修改：统一项目根目录下数据清洗模块的清洗输出即为默认输入（见 config.yaml 的 a_output）。
# 不再依赖 A 交付包与本项目平级的外部目录，保证新环境开箱即用。
DEFAULT_INPUT = PROJECT_ROOT / "data" / "carbonmonitor_clean.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "clean_data.csv"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="A 交付包 → D 统一输入")
    ap.add_argument("--input", default=str(DEFAULT_INPUT), help="A 的 clean CSV 路径")
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT), help="输出 canonical CSV 路径")
    args = ap.parse_args(argv)

    inp = Path(args.input)
    if not inp.exists():
        logger.error("找不到 A 交付数据: %s", inp)
        return 1

    raw = pd.read_csv(inp)
    df = canonicalize_raw(raw, {"data": {}})  # config 仅占位，canonicalize 不依赖其必填项

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8")
    logger.info("已写出 D 统一输入: %s  (城市=%d, 行数=%d, 时间=%s~%s)",
                out, df["city"].nunique(), len(df), df["date"].min().date(), df["date"].max().date())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
