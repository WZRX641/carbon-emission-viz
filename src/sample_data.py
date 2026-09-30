"""生成「符合 A 字段口径」的合成样例数据，用于框架验证。

⚠️ 重要：本文件产生的数据纯属合成，仅用于在没有 A/B 真实产出时
验证 D 框架能否端到端跑通。正式运行前必须替换为 A 清洗后的真实数据：
    python -m src.data_cleaning --input data/raw --output data/processed
然后把 A 输出的 clean_data.csv 放到 config.yaml 中 data.clean_input 指定的路径。

运行：
    python -m src.sample_data                 # 生成到 data/processed/clean_data.csv
    python -m src.sample_data --out 其它路径.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .utils import PROJECT_ROOT, setup_logger

logger = setup_logger()

# (城市, 国家, 基准月排放[万吨CO2], 波动系数, 季节性幅度, 峰值月, 年增长率)
# 设计多种原型，使聚类能分出有意义的不同模式。
CITIES = [
    ("Beijing",      "China",        420, 0.06, 0.35, 1,  0.02),
    ("Shanghai",     "China",        480, 0.05, 0.25, 1,  0.03),
    ("Tokyo",        "Japan",        390, 0.04, 0.20, 2,  0.01),
    ("Delhi",        "India",        350, 0.10, 0.55, 1,  0.06),
    ("Mumbai",       "India",        210, 0.09, 0.45, 1,  0.05),
    ("New York",     "USA",          450, 0.05, 0.30, 2,  0.00),
    ("Los Angeles",  "USA",          400, 0.06, 0.28, 2, -0.01),
    ("Chicago",      "USA",          300, 0.08, 0.50, 1, -0.02),
    ("London",       "UK",           280, 0.05, 0.40, 2, -0.01),
    ("Paris",        "France",       250, 0.05, 0.38, 2,  0.00),
    ("Berlin",       "Germany",      230, 0.06, 0.45, 1, -0.01),
    ("Rome",         "Italy",        180, 0.05, 0.35, 2,  0.00),
    ("Madrid",       "Spain",        170, 0.05, 0.33, 2,  0.01),
    ("Moscow",       "Russia",       360, 0.07, 0.60, 1,  0.00),
    ("Istanbul",     "Turkey",       200, 0.07, 0.40, 1,  0.03),
    ("Seoul",        "South Korea",  260, 0.05, 0.30, 1,  0.01),
    ("Tokyo2",       "Japan",        120, 0.04, 0.18, 2,  0.02),
    ("Bangkok",      "Thailand",     160, 0.06, 0.25, 1,  0.04),
    ("Jakarta",      "Indonesia",    190, 0.08, 0.20, 1,  0.05),
    ("Singapore",    "Singapore",    220, 0.04, 0.15, 2,  0.02),
    ("Dubai",        "UAE",          240, 0.06, 0.30, 1,  0.04),
    ("Riyadh",       "Saudi Arabia", 230, 0.07, 0.55, 1,  0.03),
    ("Cairo",        "Egypt",        180, 0.09, 0.50, 1,  0.03),
    ("Lagos",        "Nigeria",      120, 0.12, 0.30, 1,  0.07),
    ("Johannesburg", "South Africa", 170, 0.08, 0.45, 1,  0.01),
    ("Sao Paulo",    "Brazil",       240, 0.06, 0.22, 1,  0.02),
    ("Mexico City",  "Mexico",       230, 0.07, 0.35, 1,  0.01),
    ("Toronto",      "Canada",       200, 0.07, 0.55, 1,  0.00),
    ("Sydney",       "Australia",    190, 0.05, 0.30, 2,  0.00),
    ("Buenos Aires", "Argentina",    160, 0.07, 0.35, 1,  0.01),
]

START = "2020-01-01"
END = "2023-12-01"


def generate(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    months = pd.period_range(START, END, freq="M").to_timestamp()
    n = len(months)
    t = np.arange(n)
    rows = []
    for city, country, base, vol, seas, peak_month, growth in CITIES:
        # 季节性：以 peak_month 为峰的近似正弦
        phase = 2 * np.pi * (months.month - peak_month) / 12.0
        seasonal = 1 + seas * np.sin(phase)
        trend = 1 + growth * (t / n)
        noise = rng.normal(1.0, vol, size=n)
        emission = base * seasonal * trend * noise
        emission = np.clip(emission, base * 0.2, None)  # 非负、下限合理
        for m, val in zip(months, emission):
            rows.append({
                "city": city,
                "country": country,
                "date": m.strftime("%Y-%m-%d"),
                "year": int(m.year),
                "month": int(m.month),
                "co2_emission": round(float(val), 2),
            })
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="生成合成样例数据(框架验证用)")
    ap.add_argument("--out", default=str(PROJECT_ROOT / "data" / "processed" / "clean_data.csv"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = generate(args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8")
    logger.info("合成样例已写出: %s  (城市=%d, 行数=%d, 时间=%s~%s)",
                out, df["city"].nunique(), len(df), df["date"].min(), df["date"].max())


if __name__ == "__main__":
    main()
