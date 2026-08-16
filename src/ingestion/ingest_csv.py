"""CLI entry point for the ingestion stage.

Place this file at: src/ingestion/ingest_csv.py

This is the module the README documents (`python -m src.ingestion.ingest_csv`)
but it wasn't among the uploaded files — only validator.py, which contains the
actual load/validate/normalize logic and its own `main()`, was provided.
This is a thin wrapper so the documented command works as-is.

Usage:
    python -m src.ingestion.ingest_csv data/Bisoprolol_icsr_sample_1068rows.xlsx
    python -m src.ingestion.ingest_csv data/source.xlsx --output-dir data
"""
from __future__ import annotations

from .validator import main

if __name__ == "__main__":
    main()