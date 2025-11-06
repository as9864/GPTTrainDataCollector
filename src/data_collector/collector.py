"""Core logic for building a RAG dataset using GPT models."""

from __future__ import annotations

import json
import logging
import time
from typing import Dict, List, Set

from openai import OpenAI

from .config import CollectorConfig

LOGGER = logging.getLogger(__name__)


class DatasetCollector:
    """Collects question-answer-context triples suitable for RAG training."""

    def __init__(self, config: CollectorConfig) -> None:
        self.config = config
        self._client = OpenAI(api_key=config.openai.api_key)
        self._max_retries = max(config.openai.max_retries, 1)

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

            item = self._parse_payload(payload)
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
        return (
            f"너는 전문 데이터 큐레이터야. 아래 조건을 만족하는 RAG 학습 데이터 항목을 생성해.\n"
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
