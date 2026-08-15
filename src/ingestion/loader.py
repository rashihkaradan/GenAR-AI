"""Safe, reusable loading for the supplied ICSR line listing."""
from __future__ import annotations

from pathlib import Path
from typing import Union

import pandas as pd


SupportedPath = Union[str, Path]


class DatasetLoadError(ValueError):
    """Raised when the input dataset cannot be loaded safely."""


def load_dataset(path: SupportedPath, *, sheet_name: int | str = 0) -> pd.DataFrame:
    """Load a CSV/TSV/Excel ICSR line listing without changing the source file.

    All fields are read as pandas' nullable string type. This preserves identifiers
    (including leading zeroes) and leaves missing values explicit as ``pd.NA``.
    ``sheet_name`` applies only to Excel inputs.
    """
    source = Path(path)
    if not source.is_file():
        raise DatasetLoadError(f"Dataset not found: {source}")

    suffix = source.suffix.lower()
    try:
        if suffix == ".csv":
            frame = pd.read_csv(source, dtype="string", keep_default_na=True, na_filter=True)
        elif suffix == ".tsv":
            frame = pd.read_csv(source, sep="\t", dtype="string", keep_default_na=True, na_filter=True)
        elif suffix in {".xlsx", ".xls"}:
            frame = pd.read_excel(source, sheet_name=sheet_name, dtype="string")
        else:
            raise DatasetLoadError(f"Unsupported dataset format: {suffix or '<none>'}. Use CSV, TSV, XLSX, or XLS.")
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise DatasetLoadError(f"Could not load {source.name}: {exc}") from exc

    frame.columns = [str(column).strip() for column in frame.columns]
    if not frame.columns.is_unique:
        duplicates = frame.columns[frame.columns.duplicated()].tolist()
        raise DatasetLoadError(f"Dataset has duplicate column names: {duplicates}")
    return frame
