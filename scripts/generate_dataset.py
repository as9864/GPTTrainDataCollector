"""Entry point for generating a RAG dataset using GPT models."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / 'src'
if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))

from data_collector import CollectorConfig, DatasetCollector, ExcelWriter

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a RAG dataset via GPT models.")
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        type=Path,
        help="경로를 지정하면 커스텀 설정으로 실행할 수 있습니다.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = CollectorConfig.from_file(args.config)

    if not config.openai.api_key or config.openai.api_key == "YOUR_OPENAI_API_KEY":
        raise ValueError("config/config.yaml 파일에 OpenAI API Key를 설정해주세요.")

    LOGGER.info("Generating %s dataset items using %s", config.dataset.size, config.openai.model)

    collector = DatasetCollector(config)
    items = collector.collect()

    writer = ExcelWriter(config.dataset.output_path)
    output_path = writer.write(items)
    LOGGER.info("Dataset written to %s", output_path)


if __name__ == "__main__":
    main()
