from __future__ import annotations

import argparse
import csv
import os
import re
from pathlib import Path
from typing import Iterable

from neo4j import GraphDatabase

DEFAULT_CSV_PATH = "graph/csv/triples.csv"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"")
        if key and key not in os.environ:
            os.environ[key] = value


def load_env(var_name: str, default: str | None = None) -> str:
    value = os.getenv(var_name) or default
    if not value:
        raise SystemExit(f"Missing environment variable: {var_name}")
    return value


def iter_csv(path: Path) -> Iterable[dict]:
    for encoding in ("utf-8", "gbk"):
        try:
            with path.open("r", encoding=encoding, errors="strict") as reader:
                csv_reader = csv.DictReader(reader)
                if not csv_reader.fieldnames:
                    raise ValueError("Missing header")
                yield from csv_reader
            return
        except Exception:
            continue
    with path.open("r", encoding="utf-8", errors="replace") as reader:
        csv_reader = csv.DictReader(reader)
        yield from csv_reader


def sanitize_rel_type(text: str) -> str:
    if not text:
        return "RELATED_TO"
    cleaned = re.sub(r"[^0-9A-Za-z]+", "_", text.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned.upper() or "RELATED_TO"


def import_triples(session, triples_path: Path, batch_size: int) -> None:
    batch: list[dict] = []
    for row in iter_csv(triples_path):
        head = (row.get("head") or "").strip()
        relation = (row.get("relation") or "").strip()
        tail = (row.get("tail") or "").strip()
        if not head or not tail:
            continue
        batch.append({"head": head, "tail": tail, "relation": relation})
        if len(batch) >= batch_size:
            _insert_triples(session, batch)
            batch = []
    if batch:
        _insert_triples(session, batch)


def _insert_triples(session, rows: list[dict]) -> None:
    query = (
        "UNWIND $rows AS row "
        "MERGE (a:Entity {name: row.head}) "
        "MERGE (b:Entity {name: row.tail}) "
        "MERGE (a)-[r:RELATION {type: row.rel_type}]->(b) "
        "SET r.raw_type = row.raw_type"
    )
    payload = []
    for row in rows:
        rel_type = sanitize_rel_type(row["relation"])
        payload.append({
            "head": row["head"],
            "tail": row["tail"],
            "rel_type": rel_type,
            "raw_type": row["relation"] or rel_type
        })
    session.run(query, rows=payload)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import head/relation/tail CSV into Neo4j.")
    parser.add_argument("--csv", default=DEFAULT_CSV_PATH, help="Path to triples CSV")
    parser.add_argument("--batch", type=int, default=500, help="Batch size")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    load_env_file(Path(".env"))

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit("CSV file not found.")

    uri = load_env("NEO4J_URI", "bolt://localhost:7687")
    user = load_env("NEO4J_USER", "neo4j")
    password = load_env("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        import_triples(session, csv_path, args.batch)

    driver.close()
    print("Neo4j import completed.")


if __name__ == "__main__":
    main()
