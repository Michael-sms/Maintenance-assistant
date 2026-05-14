from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Iterable

from neo4j import GraphDatabase

DEFAULT_CSV_DIR = "graph/csv"


def iter_csv(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as reader:
        csv_reader = csv.DictReader(reader)
        for row in csv_reader:
            yield row


def load_env(var_name: str, default: str | None = None) -> str:
    value = os.getenv(var_name) or default
    if not value:
        raise SystemExit(f"Missing environment variable: {var_name}")
    return value


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


def import_nodes(session, nodes_path: Path, batch_size: int) -> None:
    batch: list[dict] = []
    for row in iter_csv(nodes_path):
        batch.append(row)
        if len(batch) >= batch_size:
            _insert_nodes(session, batch)
            batch = []
    if batch:
        _insert_nodes(session, batch)


def _insert_nodes(session, rows: list[dict]) -> None:
    query = (
        "UNWIND $rows AS row "
        "MERGE (n:Entity {id: row['id:ID']}) "
        "SET n.name = row.name, "
        "    n.type = row.type, "
        "    n.source_category = row.source_category, "
        "    n.source_file = row.source_file, "
        "    n.source_page_number = toInteger(row['source_page_number:int']), "
        "    n.confidence = toFloat(row['confidence:float'])"
    )
    session.run(query, rows=rows)


def import_relations(session, rels_path: Path, batch_size: int) -> None:
    batch: list[dict] = []
    for row in iter_csv(rels_path):
        batch.append(row)
        if len(batch) >= batch_size:
            _insert_relations(session, batch)
            batch = []
    if batch:
        _insert_relations(session, batch)


def _insert_relations(session, rows: list[dict]) -> None:
    query = (
        "UNWIND $rows AS row "
        "MATCH (a:Entity {id: row[':START_ID']}) "
        "MATCH (b:Entity {id: row[':END_ID']}) "
        "MERGE (a)-[r:RELATION {type: row[':TYPE']}]->(b) "
        "SET r.confidence = toFloat(row['confidence:float']), "
        "    r.source_category = row.source_category, "
        "    r.source_file = row.source_file, "
        "    r.source_page_number = toInteger(row['source_page_number:int'])"
    )
    session.run(query, rows=rows)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import CSV into Neo4j.")
    parser.add_argument("--csv", default=DEFAULT_CSV_DIR, help="CSV directory")
    parser.add_argument("--batch", type=int, default=500, help="Batch size")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    load_env_file(Path(".env"))

    csv_dir = Path(args.csv)
    nodes_path = csv_dir / "entities.csv"
    rels_path = csv_dir / "relations.csv"
    if not nodes_path.exists() or not rels_path.exists():
        raise SystemExit("CSV files not found. Run export_csv first.")

    uri = load_env("NEO4J_URI", "bolt://localhost:7687")
    user = load_env("NEO4J_USER", "neo4j")
    password = load_env("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        import_nodes(session, nodes_path, args.batch)
        import_relations(session, rels_path, args.batch)

    driver.close()
    print("Neo4j import completed.")


if __name__ == "__main__":
    main()
