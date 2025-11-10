"""Configuration utilities for the dataset collector."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass
class OpenAIConfig:
    """Configuration related to the OpenAI client."""

    api_key: str
    model: str
    max_retries: int = 3
    temperature: float = 0.7


@dataclass
class DatasetConfig:
    """Configuration describing the dataset to generate."""

    size: int
    output_path: Path
    base_topic: str
    instruction: str
    language: str = "ko"
    mode: str = "rag"


@dataclass
class CollectorConfig:
    """Complete configuration for the dataset collector."""

    openai: OpenAIConfig
    dataset: DatasetConfig

    @classmethod
    def from_file(cls, path: str | Path) -> "CollectorConfig":
        """Create the configuration from a YAML file."""

        raw = _read_yaml(path)
        openai_section = raw.get("openai", {})
        dataset_section = raw.get("dataset", {})
        openai_cfg = OpenAIConfig(
            api_key=openai_section.get("api_key", ""),
            model=openai_section.get("model", "gpt-4o-mini"),
            max_retries=int(openai_section.get("max_retries", 3)),
            temperature=float(openai_section.get("temperature", 0.7)),
        )
        dataset_cfg = DatasetConfig(
            size=int(dataset_section.get("size", 10)),
            output_path=Path(dataset_section.get("output_path", "output/rag_dataset.xlsx")),
            base_topic=str(dataset_section.get("base_topic", "기본 주제")),
            instruction=str(dataset_section.get("instruction", "")),
            language=str(dataset_section.get("language", "ko")),
            mode=str(dataset_section.get("mode", "rag")).lower(),
        )
        return cls(openai=openai_cfg, dataset=dataset_cfg)


def _read_yaml(path: str | Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}
