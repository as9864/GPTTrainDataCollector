"""Utilities for exporting dataset items to files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd


class ExcelWriter:
    """Write dataset items into an Excel workbook."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, rows: Iterable[Mapping[str, str]]) -> None:
        frame = pd.DataFrame(rows)
        frame.index += 1
        frame.to_excel(self.path, index=True, index_label="row")
