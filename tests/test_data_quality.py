"""集成与测试新增：数据质量测试（字段检查 + 空值处理）。

覆盖：
  1) A 的 loader 拒绝缺失必需字段的输入（字段检查）；
  2) A 的清洗逻辑正确丢弃空值/非法日期/非法数值/重复行（空值处理）；
  3) 清洗输出的 year/month/day 派生字段正确；
  4) 真实清洗数据（若已生成）的核心字段无空值、无重复行。
"""
from pathlib import Path

import pandas as pd
import pytest

from src.data_cleaning import clean_data
from src.data_loader import load_raw_csv, validate_clean_schema

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def make_dummy(path: Path) -> None:
    pd.DataFrame(
        {
            "city": ["Amsterdam", " Amsterdam ", "Beijing", None, "Beijing"],
            "date": ["01/01/2019", "02/01/2019", "bad-date", "03/01/2019", "01/01/2019"],
            "sector": ["Power", "Power", "Industry", "Power", "Industry"],
            "value": [0.5, "1.0", 2.0, None, 2.0],
            "Unnamed: 4": [None] * 5,
        }
    ).to_csv(path, index=False)


def test_load_rejects_missing_columns(tmp_path):
    """字段检查：缺 city/date/sector/value 任一列必须报错，不允许静默通过。"""
    bad = tmp_path / "bad.csv"
    bad.write_text("city,date,value\nBeijing,01/01/2019,1.0\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_raw_csv(bad)


def test_clean_handles_nulls_and_invalid(tmp_path):
    """空值处理：空 city/value、非法日期被丢弃；完全重复行去重。"""
    raw_path = tmp_path / "raw.csv"
    make_dummy(raw_path)
    clean, summary = clean_data(load_raw_csv(raw_path))

    # 5 行输入：None 城市行(其 value 也为空) + bad-date 行共 2 行无效 → 剩 3 行
    assert summary["rows_before"] == 5
    assert summary["rows_after"] == 3
    assert summary["dropped_rows"] == 2
    assert clean["city"].notna().all()
    assert clean["date"].notna().all()
    assert clean["value"].notna().all()
    assert clean.duplicated().sum() == 0
    # 城市名首尾空格被清理
    assert "Amsterdam" in set(clean["city"])
    assert " Amsterdam " not in set(clean["city"])


def test_clean_derives_time_fields(tmp_path):
    """清洗输出派生 year/month/day 字段且类型正确。"""
    raw_path = tmp_path / "raw.csv"
    make_dummy(raw_path)
    clean, _ = clean_data(load_raw_csv(raw_path))
    validate_clean_schema(clean)
    assert list(clean["year"].unique()) == [2019]
    assert clean["date"].dtype.kind == "M"


def test_real_clean_data_quality():
    """若真实清洗数据已生成（运行过 run_pipeline.py），校验核心质量约束。"""
    clean_csv = PROJECT_ROOT / "data" / "carbonmonitor_clean.csv"
    if not clean_csv.exists():
        pytest.skip("真实清洗数据尚未生成，请先运行 python run_pipeline.py")
    df = pd.read_csv(clean_csv)
    for col in ["city", "date", "sector", "value", "year", "month", "day"]:
        assert col in df.columns, f"清洗数据缺少字段 {col}"
        assert df[col].notna().all(), f"字段 {col} 存在空值"
    assert df.duplicated().sum() == 0, "清洗数据存在完全重复行"
