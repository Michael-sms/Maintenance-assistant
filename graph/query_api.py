from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase


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


def query_entity(name: str, limit: int) -> list[dict[str, Any]]:
    uri = load_env("NEO4J_URI", "bolt://localhost:7687")
    user = load_env("NEO4J_USER", "neo4j")
    password = load_env("NEO4J_PASSWORD")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    query = (
        "MATCH (n:Entity {name: $name})-[r]-(m:Entity) "
        "RETURN n.name AS source, r.type AS relation, m.name AS target "
        "LIMIT $limit"
    )
    with driver.session() as session:
        records = session.run(query, name=name, limit=limit)
        results = [dict(record) for record in records]
    driver.close()
    return results


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query Neo4j by entity name.")
    parser.add_argument("--name", required=True, help="Entity name")
    parser.add_argument("--limit", type=int, default=20, help="Result limit")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    load_env_file(Path(".env"))
    results = query_entity(args.name, args.limit)
    for row in results:
        print(f"{row['source']} -[{row['relation']}]-> {row['target']}")


if __name__ == "__main__":
    main()
