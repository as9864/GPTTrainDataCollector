"""Configuration utilities for the dataset collector."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


DEFAULT_OMOP_TABLES = [
    "cdm.person(person_id, gender_concept_id, year_of_birth, race_concept_id, ethnicity_concept_id)",
    "cdm.observation_period(person_id, observation_period_start_date, observation_period_end_date)",
    "cdm.visit_occurrence(visit_occurrence_id, person_id, visit_concept_id, visit_start_date, visit_end_date)",
    "cdm.condition_occurrence(condition_occurrence_id, person_id, condition_concept_id, condition_start_date, condition_type_concept_id)",
    "cdm.drug_exposure(drug_exposure_id, person_id, drug_concept_id, drug_exposure_start_date, drug_type_concept_id)",
    "cdm.procedure_occurrence(procedure_occurrence_id, person_id, procedure_concept_id, procedure_date, procedure_type_concept_id)",
    "cdm.measurement(measurement_id, person_id, measurement_concept_id, measurement_date, value_as_number)",
    "cdm.observation(observation_id, person_id, observation_concept_id, observation_date, value_as_string)",
    "cdm.device_exposure(device_exposure_id, person_id, device_concept_id, device_exposure_start_date)",
    "cdm.death(person_id, death_date, cause_concept_id)",
]


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
class SQLValidationConfig:
    """Configuration describing SQL validation behaviour."""

    enabled: bool = False
    database_url: str = ""
    search_path: Optional[str] = None
    statement_timeout_ms: int = 5000


@dataclass
class SQLConfig:
    """Configuration specific to SQL dataset generation."""

    omop_tables: List[str] = field(default_factory=list)
    validation: SQLValidationConfig = field(default_factory=SQLValidationConfig)


@dataclass
class CollectorConfig:
    """Complete configuration for the dataset collector."""

    openai: OpenAIConfig
    dataset: DatasetConfig
    sql: SQLConfig = field(default_factory=SQLConfig)

    @classmethod
    def from_file(cls, path: str | Path) -> "CollectorConfig":
        """Create the configuration from a YAML file."""

        raw = _read_yaml(path)
        openai_section = raw.get("openai", {})
        dataset_section = raw.get("dataset", {})
        sql_section = raw.get("sql", {})
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
        validation_section = sql_section.get("validation", {})
        omop_tables = sql_section.get("omop_tables") or []
        if not isinstance(omop_tables, list):
            omop_tables = [str(omop_tables)]
        omop_tables = [str(item) for item in omop_tables if str(item).strip()]
        if not omop_tables:
            omop_tables = DEFAULT_OMOP_TABLES.copy()
        sql_cfg = SQLConfig(
            omop_tables=omop_tables,
            validation=SQLValidationConfig(
                enabled=bool(validation_section.get("enabled", False)),
                database_url=str(validation_section.get("database_url", "")),
                search_path=(
                    str(validation_section.get("search_path"))
                    if validation_section.get("search_path") is not None
                    else None
                ),
                statement_timeout_ms=int(validation_section.get("statement_timeout_ms", 5000)),
            ),
        )
        return cls(openai=openai_cfg, dataset=dataset_cfg, sql=sql_cfg)


def _read_yaml(path: str | Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}
