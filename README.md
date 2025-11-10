# GPT Train Data Collector

LLM 기반 질문을 활용하여 RAG 학습 데이터셋을 자동으로 생성하는 Python 프로젝트입니다. OpenAI GPT 모델에 질의를 보내어 질문/답변/컨텍스트 조합을 만들고, 최종 결과는 엑셀 파일로 저장합니다.

## 주요 기능

- **구성 파일 기반 실행**: `config/config.yaml`에서 API Key, 모델, 생성 건수, 출력 경로 등 설정을 관리합니다.
- **중복 방지 로직**: 이미 생성된 질문은 다시 수집하지 않도록 필터링합니다.
- **엑셀 출력**: 수집된 데이터를 `output/` 디렉터리 아래 엑셀 파일로 저장합니다.

## 프로젝트 구조

```
GPTTrainDataCollector/
├── config/
│   └── config.yaml            # 실행에 필요한 설정
├── output/                    # 생성된 엑셀 파일이 저장되는 경로
├── scripts/
│   └── generate_dataset.py    # 실행 스크립트
└── src/
    └── data_collector/
        ├── __init__.py
        ├── collector.py
        ├── config.py
        └── writer.py
```

## 사전 준비

1. Python 3.10 이상을 설치합니다.
2. 의존성 설치:

```bash
pip install .
```

3. `config/config.yaml` 파일의 `openai.api_key` 값을 본인의 OpenAI API Key로 변경합니다.

## 사용 방법

```bash
python scripts/generate_dataset.py --config config/config.yaml
```

- `dataset.size`: 생성할 데이터 항목 수를 지정합니다.
- `dataset.output_path`: 결과 엑셀 파일 경로를 지정합니다.
- `dataset.base_topic`: 데이터의 기본 주제를 설정합니다.
- `dataset.instruction`: LLM에게 부가적으로 전달하고 싶은 지침을 작성합니다.
- `dataset.mode`: `rag`(기본값) 또는 `sql`을 지정하여 생성할 데이터 형식을 선택합니다.

## 출력 형식

생성된 엑셀 파일에는 다음 열이 포함됩니다.

- `row`: 데이터의 순번
- `question`: 학습에 사용할 질문
- `answer`: 질문에 대한 모범 답변 (RAG 모드)
- `context`: RAG 검색이 반환할 수 있는 참고 문단 (RAG 모드)
- `reference_title`: 컨텍스트와 관련된 출처 제목 (RAG 모드)
- `generated_sql`: 질문에 대응하는 SQL 쿼리 (SQL 모드)
- `explanation`: SQL 쿼리 설명 (SQL 모드)

## SQL 질문/응답 데이터 수집 예시

`dataset.mode`를 `sql`로 설정하면 자연어 질문과 이에 대응하는 SQL 쿼리/설명을 생성합니다. 예를 들어 `config/config.yaml`을 다음과 같이 수정할 수 있습니다.

```yaml
dataset:
  size: 20
  output_path: "output/sql_dataset.xlsx"
  base_topic: "OMOP CDM 예시 쿼리"
  instruction: |
    OMOP CDM 스키마(cdm.*)를 활용하여 의료 통계를 분석하는 SQL 예제를 작성해줘.
  language: "ko"
  mode: "sql"
```

이 설정으로 실행하면 각 행에 `question`, `generated_sql`, `explanation` 열이 포함된 엑셀 파일이 생성되어 SQL 질의-응답 학습용 데이터셋을 구축할 수 있습니다.

## 주의 사항

- OpenAI API 호출에는 비용이 발생하므로 사용 전에 요금 정책을 확인하세요.
- 네트워크 오류 등으로 실패할 경우 자동으로 재시도하지만, 반복 실패 시 예외가 발생합니다.
