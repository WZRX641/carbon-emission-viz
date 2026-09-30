"""Clean Carbon Monitor Cities data and write reproducible quality outputs."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

# 兼容两种运行方式：包内运行(python -m src.data_cleaning)与 src 目录下直接运行
try:
    from .data_loader import load_many  # type: ignore
except ImportError:  # pragma: no cover - 直接在 src/ 目录下运行时
    from data_loader import load_many  # type: ignore

CORE = ["city", "date", "sector", "value"]


def clean_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Return cleaned data and an auditable quality summary."""
    before = len(raw)
    df = raw.copy()
    # Drop spreadsheet artefacts such as Unnamed: 4, but retain meaningful fields.
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed:")], errors="ignore")
    missing = [c for c in CORE if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["city"] = df["city"].astype("string").str.strip()
    df["sector"] = df["sector"].astype("string").str.strip()
    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y", errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    invalid_date = int(df["date"].isna().sum())
    invalid_value = int(df["value"].isna().sum())
    missing_core = int(df[CORE].isna().any(axis=1).sum())
    negative_values = int((df["value"] < 0).sum())
    duplicate_rows = int(df.duplicated().sum())

    df = df.dropna(subset=CORE).drop_duplicates()
    # Negative emissions are retained for auditability because inventories may
    # contain net-removal values; they are reported rather than silently clipped.
    df["year"] = df["date"].dt.year.astype("int16")
    df["month"] = df["date"].dt.month.astype("int8")
    df["day"] = df["date"].dt.day.astype("int8")
    df = df.sort_values(["date", "city", "sector"]).reset_index(drop=True)

    summary = {
        "rows_before": before,
        "rows_after": len(df),
        "dropped_rows": before - len(df),
        "cities": int(df["city"].nunique()),
        "sectors": int(df["sector"].nunique()),
        "date_min": df["date"].min().date().isoformat() if len(df) else None,
        "date_max": df["date"].max().date().isoformat() if len(df) else None,
        "invalid_dates": invalid_date,
        "invalid_values": invalid_value,
        "rows_with_missing_core": missing_core,
        "duplicate_rows_before_drop": duplicate_rows,
        "negative_values_reported": negative_values,
        "value_min": float(df["value"].min()) if len(df) else None,
        "value_max": float(df["value"].max()) if len(df) else None,
    }
    return df, summary


def run(input_path: str | Path, output_dir: str | Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cleaned, summary = clean_data(load_many(input_path))
    cleaned.to_csv(output_dir / "carbonmonitor_clean.csv", index=False, date_format="%Y-%m-%d")
    pd.DataFrame([summary]).to_csv(output_dir / "quality_summary.csv", index=False)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean Carbon Monitor Cities CSV data")
    parser.add_argument("--input", required=True, help="CSV file or directory containing CSV files")
    parser.add_argument("--output", required=True, help="Output directory")
    args = parser.parse_args()
    summary = run(args.input, args.output)
    print(pd.Series(summary).to_string())


if __name__ == "__main__":
    main()
