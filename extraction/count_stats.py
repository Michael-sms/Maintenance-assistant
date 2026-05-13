from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

DEFAULT_OUTPUT_DIR = "data/annotations"


def iter_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as reader:
        for line in reader:
            if line.strip():
                yield json.loads(line)


def count_entities(entities_path: Path) -> int:
    ids = set()
    for item in iter_jsonl(entities_path):
        entity_id = item.get("id")
        if entity_id:
            ids.add(entity_id)
    return len(ids)


def count_relations(relations_path: Path) -> int:
    pairs = set()
    for item in iter_jsonl(relations_path):
        rel_type = item.get("type")
        from_id = item.get("from_id")
        to_id = item.get("to_id")
        if rel_type and from_id and to_id:
            pairs.add((rel_type, from_id, to_id))
    return len(pairs)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Count extracted entities and relations.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="Annotations directory")
    parser.add_argument("--entities", default="entities_dedup.jsonl", help="Entities file")
    parser.add_argument("--relations", default="relations_dedup.jsonl", help="Relations file")
    return parser


def normalize_output_dir(path: Path) -> Path:
    if path.exists():
        return path
    if path.name == "annotation":
        alt = path.with_name("annotations")
        if alt.exists():
            return alt
    return path


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    output_dir = normalize_output_dir(Path(args.output))
    entities_path = output_dir / args.entities
    relations_path = output_dir / args.relations

    if not output_dir.exists():
        raise SystemExit(f"Output directory not found: {output_dir}")
    if not entities_path.exists():
        raise SystemExit(f"Entities file not found: {entities_path}")
    if not relations_path.exists():
        raise SystemExit(f"Relations file not found: {relations_path}")

    entity_count = count_entities(entities_path)
    relation_count = count_relations(relations_path)

    print(f"Entities: {entity_count}")
    print(f"Relations: {relation_count}")
    print("Meets concept >= 200:", "YES" if entity_count >= 200 else "NO")
    print("Meets relation >= 400:", "YES" if relation_count >= 400 else "NO")


if __name__ == "__main__":
    main()
