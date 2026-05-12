from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

DEFAULT_INPUT_DIR = "知识图谱构建数据集"
DEFAULT_OUTPUT_DIR = "data/cleaned"
SENTENCE_FILE = "sentences.jsonl"


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    text = text.replace("\n", "\n")
    parts = re.split(r"(?<=[。！？!?；;])\s*", text)
    sentences: list[str] = []
    for part in parts:
        for line in part.split("\n"):
            sentence = line.strip()
            if sentence:
                sentences.append(sentence)
    return sentences


def iter_text_files(input_dir: Path) -> Iterable[Path]:
    for path in input_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".txt", ".md"}:
            yield path


def preprocess(input_dir: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    sentences_path = output_dir / SENTENCE_FILE
    with sentences_path.open("w", encoding="utf-8") as writer:
        for file_path in iter_text_files(input_dir):
            rel_path = file_path.relative_to(input_dir)
            cleaned_path = output_dir / rel_path
            cleaned_path.parent.mkdir(parents=True, exist_ok=True)
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            cleaned = normalize_text(text)
            cleaned_path.write_text(cleaned, encoding="utf-8")
            sentences = split_sentences(cleaned)
            for idx, sentence in enumerate(sentences):
                record = {
                    "id": f"{rel_path.as_posix()}::{idx}",
                    "sentence": sentence,
                    "source_file": rel_path.as_posix(),
                    "index": idx,
                }
                writer.write(json.dumps(record, ensure_ascii=False) + "\n")
    return sentences_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preprocess raw texts and split sentences.")
    parser.add_argument("--input", default=DEFAULT_INPUT_DIR, help="Input dataset directory")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="Output cleaned directory")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    if not input_dir.exists():
        raise SystemExit(f"Input directory not found: {input_dir}")
    sentences_path = preprocess(input_dir, output_dir)
    print(f"Sentences saved to {sentences_path}")


if __name__ == "__main__":
    main()
