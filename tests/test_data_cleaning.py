"""Basic tests for the data cleaning module."""
import sys
from pathlib import Path
import tempfile
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_cleaning import clean_data  # noqa: E402
from data_loader import load_raw_csv  # noqa: E402


def make_dummy(path: Path) -> None:
    pd.DataFrame(
        {
            "city": ["Amsterdam", " Amsterdam ", "Beijing", None],
            "date": ["01/01/2019", "02/01/2019", "bad-date", "03/01/2019"],
            "sector": ["Power", "Power", "Industry", "Power"],
            "value": [0.5, "1.0", 2.0, None],
            "Unnamed: 4": [None, None, None, None],
        }
    ).to_csv(path, index=False)


def test_load_and_clean(tmpdir) -> None:
    raw_path = Path(tmpdir) / "raw.csv"
    make_dummy(raw_path)
    raw = load_raw_csv(raw_path)
    clean, summary = clean_data(raw)
    assert "Unnamed: 4" not in clean.columns
    assert summary["rows_before"] == 4
    assert summary["dropped_rows"] >= 1
    assert clean["date"].dtype.kind == "M"


def test_quality_summary_fields(tmpdir) -> None:
    raw_path = Path(tmpdir) / "raw.csv"
    make_dummy(raw_path)
    _, summary = clean_data(load_raw_csv(raw_path))
    for field in ["rows_before", "rows_after", "cities", "invalid_dates", "duplicate_rows_before_drop"]:
        assert field in summary


if __name__ == "__main__":
    test_load_and_clean(tempfile.mkdtemp())
    test_quality_summary_fields(tempfile.mkdtemp())
    print("tests OK")
