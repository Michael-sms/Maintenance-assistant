from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

DEFAULT_OUTPUT_DIR = "data/annotations"


def iter_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as reader:
        for line in reader:
            if line.strip():
                yield json.loads(line)


def dedup_entities(entities_path: Path) -> list[dict]:
    merged = {}
    for entity in iter_jsonl(entities_path):
        key = entity["id"]
        item = merged.get(key)
        if item is None:
            merged[key] = {
                **entity,
                "mention_count": 1,
                "sources": {entity["source_file"]},
            }
        else:
            item["mention_count"] += 1
            item["sources"].add(entity["source_file"])
            item["confidence"] = max(item.get("confidence", 0), entity.get("confidence", 0))
    for value in merged.values():
        value["sources"] = sorted(value["sources"])
    return list(merged.values())


def dedup_relations(relations_path: Path) -> list[dict]:
    merged = {}
    for relation in iter_jsonl(relations_path):
        key = (relation["type"], relation["from_id"], relation["to_id"])
        item = merged.get(key)
        if item is None:
            merged[key] = {
                **relation,
                "support_count": 1,
                "evidence": {relation["sentence"]},
            }
        else:
            item["support_count"] += 1
            item["evidence"].add(relation["sentence"])
            item["confidence"] = max(item.get("confidence", 0), relation.get("confidence", 0))
    for value in merged.values():
        value["evidence"] = sorted(value["evidence"])[:5]
    return list(merged.values())


def write_jsonl(records: Iterable[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as writer:
        for record in records:
            writer.write(json.dumps(record, ensure_ascii=False) + "\n")


def run(output_dir: Path) -> tuple[Path, Path]:
    entities_path = output_dir / "entities.jsonl"
    relations_path = output_dir / "relations.jsonl"
    if not entities_path.exists() or not relations_path.exists():
        raise SystemExit("Missing entities/relations. Run extraction first.")

    dedup_entities_path = output_dir / "entities_dedup.jsonl"
    dedup_relations_path = output_dir / "relations_dedup.jsonl"

    write_jsonl(dedup_entities(entities_path), dedup_entities_path)
    write_jsonl(dedup_relations(relations_path), dedup_relations_path)

    return dedup_entities_path, dedup_relations_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deduplicate entities and relations.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="Output directory")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    entities_path, relations_path = run(Path(args.output))
    print(f"Dedup entities: {entities_path}")
    print(f"Dedup relations: {relations_path}")


if __name__ == "__main__":
    main()
