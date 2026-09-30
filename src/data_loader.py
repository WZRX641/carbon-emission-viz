"""Load and validate Carbon Monitor Cities CSV data."""
from pathlib import Path
from typing import Iterable
import pandas as pd

REQUIRED_COLUMNS = ["city", "date", "sector", "value"]
OPTIONAL_COLUMNS = ["country", "latitude", "longitude"]


def load_raw_csv(path: str | Path) -> pd.DataFrame:
    """Read a CSV and validate the required schema."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input file does not exist: {path}")
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return df


def validate_clean_schema(df: pd.DataFrame) -> None:
    required = ["city", "date", "year", "month", "sector", "value"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Clean data is missing columns: {missing}")


def find_csv_files(input_path: str | Path) -> list[Path]:
    path = Path(input_path)
    if path.is_file():
        return [path]
    files = sorted(path.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found under: {path}")
    return files


def load_many(input_path: str | Path) -> pd.DataFrame:
    frames = [load_raw_csv(p) for p in find_csv_files(input_path)]
    return pd.concat(frames, ignore_index=True)
