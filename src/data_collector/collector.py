"""Core logic for building a RAG dataset using GPT models."""

from __future__ import annotations

import json
import logging
import time
from typing import Dict, List, Optional, Set, Tuple

from openai import OpenAI
import psycopg

from .config import CollectorConfig, SQLValidationConfig

LOGGER = logging.getLogger(__name__)


class SQLValidator:
    """Validate generated SQL statements against a PostgreSQL database."""

    def __init__(self, config: SQLValidationConfig) -> None:
        if not config.database_url:
            raise ValueError("database_url must be provided when SQL validation is enabled")
        self._config = config

    def validate(self, query: str) -> Tuple[bool, str]:
        statement = query.strip()
        if not statement:
            return False, "생성된 SQL이 비어 있습니다."

        statement = statement.rstrip(";")
        if ";" in statement:
            return False, "하나의 SQL 문장만 생성해 주세요."

        tokens = statement.split()
        first_token = tokens[0].upper() if tokens else ""
        if first_token not in {"SELECT", "WITH"}:
            return False, "데이터 조회용 SELECT 혹은 WITH 문만 지원합니다."

        try:
            with psycopg.connect(self._config.database_url) as conn:
                with conn.cursor() as cursor:
                    if self._config.search_path:
                        cursor.execute(f"SET search_path TO {self._config.search_path}")
                    if self._config.statement_timeout_ms:
                        cursor.execute(
                            "SET LOCAL statement_timeout = %s",
                            (int(self._config.statement_timeout_ms),),
                        )
                    cursor.execute("EXPLAIN (FORMAT JSON) " + statement)
                    cursor.fetchall()
        except psycopg.Error as exc:  # pragma: no cover - requires DB connection
            return False, str(exc).strip()

        return True, ""


class DatasetCollector:
    """Collects question-answer-context triples suitable for RAG training."""

    def __init__(self, config: CollectorConfig) -> None:
        self.config = config
        self._client = OpenAI(api_key=config.openai.api_key)
        self._max_retries = max(config.openai.max_retries, 1)
        self._sql_validator: Optional[SQLValidator] = None
        if (
            self.config.dataset.mode == "sql"
            and self.config.sql.validation.enabled
        ):
            try:
                self._sql_validator = SQLValidator(self.config.sql.validation)
            except ValueError as exc:
                LOGGER.warning("SQL validator disabled: %s", exc)

    def collect(self) -> List[Dict[str, str]]:
        """Collect the dataset items using the configured GPT model."""

        results: List[Dict[str, str]] = []
        seen_questions: Set[str] = set()
        target_size = self.config.dataset.size
        consecutive_failures = 0

        while len(results) < target_size:
            prompt = self._build_prompt(index=len(results) + 1)
            LOGGER.debug("Generated prompt: %s", prompt)

            try:
                payload = self._call_model(prompt)
                consecutive_failures = 0
            except Exception as exc:  # pragma: no cover - network failure handling
                consecutive_failures += 1
                LOGGER.warning("Model call failed (%s/%s): %s", consecutive_failures, self._max_retries, exc)
                if consecutive_failures >= self._max_retries:
                    raise
                time.sleep(2.0)
                continue

            try:
                item = self._parse_payload(payload)
            except ValueError as exc:
                LOGGER.warning("Skipping unparsable payload: %s", exc)
                continue
            question = item.get("question", "").strip()
            if not question:
                LOGGER.debug("Skipping empty question payload: %s", payload)
                continue
            if question in seen_questions:
                LOGGER.info("Duplicate question detected, retrying: %s", question)
                continue

            seen_questions.add(question)
            results.append(item)

        return results

    def _build_prompt(self, index: int) -> str:
        dataset_cfg = self.config.dataset
        if dataset_cfg.mode == "sql":
            table_guidance = ""
            if self.config.sql.omop_tables:
                table_list = "\n".join(f"  - {entry}" for entry in self.config.sql.omop_tables)
                table_guidance = (
                    "- 사용할 수 있는 OMOP CDM 테이블과 주요 컬럼 목록:\n"
                    f"{table_list}\n"
                    "- 위 목록에 없는 테이블이나 컬럼은 사용하지 마.\n"
                )
            return (
                "너는 의료 데이터베이스 전문가이자 SQL 튜터야. 아래 조건을 만족하는 학습 데이터를 생성해.\n"
                f"- 주제: {dataset_cfg.base_topic}\n"
                f"- 언어: {dataset_cfg.language}\n"
                "- JSON 객체 하나만 출력해. 키는 question, generated_sql, explanation.\n"
                "- question은 사용자가 자연어로 SQL을 요청하는 문장으로 작성해.\n"
                "- generated_sql에는 질문을 해결하기 위한 실행 가능한 SQL 쿼리만 포함해.\n"
                "- explanation에는 쿼리의 동작을 간단한 한국어 문장으로 설명해.\n"
                "- question은 서로 중복되지 않도록 고유하게 작성해.\n"
                "- 모든 테이블은 cdm.<table_name> 형태로 작성하고, 존재하는 컬럼만 사용해.\n"
                f"{table_guidance}"
                f"- 데이터 세트 내 인덱스: {index}.\n"
                f"추가 지침: {dataset_cfg.instruction.strip()}"
            )

        return (
            "너는 전문 데이터 큐레이터야. 아래 조건을 만족하는 RAG 학습 데이터 항목을 생성해.\n"
            f"- 주제: {dataset_cfg.base_topic}\n"
            f"- 언어: {dataset_cfg.language}\n"
            "- JSON 객체 하나만 출력해. 키는 question, answer, context, reference_title.\n"
            "- context는 RAG 검색이 반환할 수 있는 문단 형태로 작성해.\n"
            "- reference_title은 context에 해당하는 간단한 출처 제목으로 작성해.\n"
            "- question은 서로 중복되지 않도록 고유하게 작성해.\n"
            "- answer는 context를 근거로 명확하게 답해.\n"
            f"- 데이터 세트 내 인덱스: {index}.\n"
            f"추가 지침: {dataset_cfg.instruction.strip()}"
        )

    def _call_model(self, prompt: str) -> str:
        response = self._client.responses.create(
            model=self.config.openai.model,
            input=prompt,
            temperature=self.config.openai.temperature,
        )
        if hasattr(response, "output_text"):
            return response.output_text
        # Fallback for legacy structures
        try:
            return "".join(
                part.text
                for part in getattr(response, "output", [])
                for item in getattr(part, "content", [])
                if hasattr(item, "text")
            )
        except Exception as exc:  # pragma: no cover - defensive branch
            raise ValueError("Unexpected response format") from exc

    def _parse_payload(self, payload: str) -> Dict[str, str]:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            LOGGER.debug("Payload was not pure JSON, attempting to extract JSON block.")
            data = self._extract_json(payload)
        if self.config.dataset.mode == "sql":
            generated_sql = data.get("generated_sql") or data.get("sql")
            item = {
                "question": str(data.get("question", "")).strip(),
                "generated_sql": str(generated_sql or "").strip(),
                "explanation": str(data.get("explanation", "")).strip(),
            }
            item.update(self._validate_sql(item.get("generated_sql", "")))
            return item

        return {
            "question": str(data.get("question", "")).strip(),
            "answer": str(data.get("answer", "")).strip(),
            "context": str(data.get("context", "")).strip(),
            "reference_title": str(data.get("reference_title", "")).strip(),
        }

    def _extract_json(self, payload: str) -> Dict[str, str]:
        start = payload.find("{")
        end = payload.rfind("}")
        if start == -1 or end == -1 or start >= end:
            raise ValueError("응답에서 JSON 객체를 찾을 수 없습니다.")
        return json.loads(payload[start : end + 1])

    def _validate_sql(self, query: str) -> Dict[str, object]:
        if not self._sql_validator:
            return {"sql_is_valid": None, "sql_validation_error": ""}

        is_valid, message = self._sql_validator.validate(query)
        if not is_valid:
            LOGGER.warning("SQL validation failed: %s", message)
        return {
            "sql_is_valid": is_valid,
            "sql_validation_error": "" if is_valid else message,
        }
