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

    def write(self, rows: Iterable[Mapping[str, str]]) -> Path:
        target_path = self._resolve_path()
        frame = pd.DataFrame(rows)
        frame.index += 1
        frame.to_excel(target_path, index=True, index_label="row")
        return target_path

    def _resolve_path(self) -> Path:
        if not self.path.exists():
            return self.path

        suffix = "".join(self.path.suffixes) or ""
        stem = self.path.name[: -len(suffix)] if suffix else self.path.name
        parent = self.path.parent
        counter = 1
        while True:
            candidate_name = f"{stem}_{counter}{suffix}"
            candidate_path = parent / candidate_name
            if not candidate_path.exists():
                return candidate_path
            counter += 1
