from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable

DEFAULT_OUTPUT_DIR = "graph/csv"
DEFAULT_ANNOTATIONS_DIR = "data/annotations"


def iter_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as reader:
        for line in reader:
            if line.strip():
                yield json.loads(line)


def export_entities(entities_path: Path, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id:ID",
        "name",
        "type",
        "source_category",
        "source_file",
        "source_page_number:int",
        "confidence:float",
    ]
    count = 0
    with output_path.open("w", encoding="utf-8", newline="") as writer:
        csv_writer = csv.DictWriter(writer, fieldnames=fieldnames)
        csv_writer.writeheader()
        for item in iter_jsonl(entities_path):
            csv_writer.writerow(
                {
                    "id:ID": item.get("id"),
                    "name": item.get("name"),
                    "type": item.get("type"),
                    "source_category": ";".join(item.get("categories", []) or [item.get("source_category", "")] ).strip(";"),
                    "source_file": ";".join(item.get("sources", []) or [item.get("source_file", "")] ).strip(";"),
                    "source_page_number:int": (item.get("source_page_number") if isinstance(item.get("source_page_number"), int) else None),
                    "confidence:float": item.get("confidence"),
                }
            )
            count += 1
    return count


def export_relations(relations_path: Path, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        ":START_ID",
        ":END_ID",
        ":TYPE",
        "confidence:float",
        "source_category",
        "source_file",
        "source_page_number:int",
    ]
    count = 0
    with output_path.open("w", encoding="utf-8", newline="") as writer:
        csv_writer = csv.DictWriter(writer, fieldnames=fieldnames)
        csv_writer.writeheader()
        for item in iter_jsonl(relations_path):
            csv_writer.writerow(
                {
                    ":START_ID": item.get("from_id"),
                    ":END_ID": item.get("to_id"),
                    ":TYPE": item.get("type"),
                    "confidence:float": item.get("confidence"),
                    "source_category": ";".join(item.get("categories", []) or [item.get("source_category", "")] ).strip(";"),
                    "source_file": item.get("source_file", ""),
                    "source_page_number:int": (item.get("source_page_number") if isinstance(item.get("source_page_number"), int) else None),
                }
            )
            count += 1
    return count


def export_triples(relations_path: Path, output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [":START_ID", ":TYPE", ":END_ID"]
    count = 0
    with output_path.open("w", encoding="utf-8", newline="") as writer:
        csv_writer = csv.DictWriter(writer, fieldnames=fieldnames)
        csv_writer.writeheader()
        for item in iter_jsonl(relations_path):
            start_id = item.get("from_id")
            end_id = item.get("to_id")
            rel_type = item.get("type")
            if not (start_id and end_id and rel_type):
                continue
            csv_writer.writerow(
                {
                    ":START_ID": start_id,
                    ":TYPE": rel_type,
                    ":END_ID": end_id,
                }
            )
            count += 1
    return count


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export entities/relations to CSV for Neo4j import.")
    parser.add_argument("--annotations", default=DEFAULT_ANNOTATIONS_DIR, help="Annotations directory")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="Output CSV directory")
    parser.add_argument("--entities", default="entities_dedup.jsonl", help="Entities JSONL file")
    parser.add_argument("--relations", default="relations_dedup.jsonl", help="Relations JSONL file")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    annotations_dir = Path(args.annotations)
    output_dir = Path(args.output)
    entities_path = annotations_dir / args.entities
    relations_path = annotations_dir / args.relations

    if not entities_path.exists():
        raise SystemExit(f"Entities file not found: {entities_path}")
    if not relations_path.exists():
        raise SystemExit(f"Relations file not found: {relations_path}")

    nodes_csv = output_dir / "entities.csv"
    rels_csv = output_dir / "relations.csv"
    triples_csv = output_dir / "triples.csv"

    entity_count = export_entities(entities_path, nodes_csv)
    relation_count = export_relations(relations_path, rels_csv)
    triples_count = export_triples(relations_path, triples_csv)

    print(f"Exported entities: {entity_count} -> {nodes_csv}")
    print(f"Exported relations: {relation_count} -> {rels_csv}")
    print(f"Exported triples: {triples_count} -> {triples_csv}")


if __name__ == "__main__":
    main()
