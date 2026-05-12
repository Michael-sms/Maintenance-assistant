from __future__ import annotations

import argparse
from pathlib import Path

from extraction.entity_extract import run as run_entity_extract
from extraction.fusion import run as run_fusion
from extraction.preprocess import preprocess
from extraction.relation_extract import run as run_relation_extract

DEFAULT_INPUT_DIR = "知识图谱构建数据集"
DEFAULT_DATA_DIR = "data"


def run_pipeline(input_dir: Path, data_dir: Path, lexicon_dir: Path) -> None:
    cleaned_dir = data_dir / "cleaned"
    annotations_dir = data_dir / "annotations"

    preprocess(input_dir, cleaned_dir)
    run_entity_extract(cleaned_dir, annotations_dir, lexicon_dir)
    run_relation_extract(cleaned_dir, annotations_dir)
    run_fusion(annotations_dir)


def run_demo(data_dir: Path) -> None:
    demo_input = data_dir / "raw"
    demo_input.mkdir(parents=True, exist_ok=True)
    demo_file = demo_input / "demo.txt"
    demo_file.write_text(
        "燃油泵故障表现为推力不足。由于燃油压力不足导致燃油泵失效。"
        "维修时更换燃油泵并使用扭矩扳手，适用于某型飞行器。",
        encoding="utf-8",
    )
    run_pipeline(demo_input, data_dir, Path("extraction/lexicon"))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run extraction pipeline.")
    parser.add_argument("--input", default=DEFAULT_INPUT_DIR, help="Input dataset directory")
    parser.add_argument("--data", default=DEFAULT_DATA_DIR, help="Data output base directory")
    parser.add_argument("--lexicon", default="extraction/lexicon", help="Optional lexicon directory")
    parser.add_argument("--demo", action="store_true", help="Run demo with a sample text")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    data_dir = Path(args.data)

    if args.demo:
        run_demo(data_dir)
        print("Demo completed.")
        return

    input_dir = Path(args.input)
    if not input_dir.exists():
        raise SystemExit(f"Input directory not found: {input_dir}")

    run_pipeline(input_dir, data_dir, Path(args.lexicon))
    print("Pipeline completed.")


if __name__ == "__main__":
    main()
