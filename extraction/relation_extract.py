from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List

DEFAULT_OUTPUT_DIR = "data/annotations"
DEFAULT_CLEAN_DIR = "data/cleaned"
SENTENCE_FILE = "sentences.jsonl"

KEYWORDS = {
    "CAUSES": ["导致", "引起"],
    "MANIFESTS_AS": ["表现为", "症状为"],
    "HAS_COMPONENT": ["包含", "包括", "由"],
    "HAS_SYSTEM": ["系统"],
    "HAS_SUBSYSTEM": ["子系统"],
    "PART_OF": ["属于", "隶属"],
    "APPLICABLE_TO": ["适用于"],
    "USES_PROCEDURE": ["按照", "依照", "依据"],
    "REQUIRES_TOOL": ["使用", "需要"],
    "REQUIRES_MATERIAL": ["需要", "涂覆", "使用"],
    "OCCURS_IN": ["发生在", "位于"],
    "HAS_SOLUTION": ["处理", "维修", "更换", "修复"],
    "AFFECTS": ["影响", "导致", "引起", "使"],
    "MEASURED_BY": ["参数", "指标", "检测", "测量"],
}


def iter_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as reader:
        for line in reader:
            if line.strip():
                yield json.loads(line)


def group_entities(entities: Iterable[dict]) -> Dict[str, List[dict]]:
    grouped: Dict[str, List[dict]] = defaultdict(list)
    for entity in entities:
        grouped[entity["type"]].append(entity)
    return grouped


def sentence_contains(sentence: str, keywords: List[str]) -> bool:
    return any(keyword in sentence for keyword in keywords)


def extract_relations(
    sentence: str,
    entities: List[dict],
    source_file: str,
    source_category: str,
    sentence_id: str,
    source_page_index: int | None,
    source_page_number: int | None,
) -> List[dict]:
    grouped = group_entities(entities)
    relations: List[dict] = []

    def add_relation(
        rel_type: str,
        from_entities: List[dict],
        to_entities: List[dict],
        confidence: float = 0.5,
    ) -> None:
        for source in from_entities:
            for target in to_entities:
                relations.append(
                    {
                        "type": rel_type,
                        "from_id": source["id"],
                        "from_name": source["name"],
                        "from_type": source["type"],
                        "to_id": target["id"],
                        "to_name": target["name"],
                        "to_type": target["type"],
                        "sentence_id": sentence_id,
                        "sentence": sentence,
                        "source_file": source_file,
                        "source_category": source_category,
                        "source_page_index": source_page_index,
                        "source_page_number": source_page_number,
                        "confidence": confidence,
                    }
                )

    if sentence_contains(sentence, KEYWORDS["CAUSES"]):
        add_relation("CAUSES", grouped.get("FaultCause", []), grouped.get("FaultMode", []), 0.6)
    if sentence_contains(sentence, KEYWORDS["MANIFESTS_AS"]):
        add_relation("MANIFESTS_AS", grouped.get("FaultMode", []), grouped.get("FaultSymptom", []), 0.6)
    if sentence_contains(sentence, KEYWORDS["HAS_COMPONENT"]):
        add_relation("HAS_COMPONENT", grouped.get("System", []) + grouped.get("Subsystem", []), grouped.get("Component", []), 0.6)
    if sentence_contains(sentence, KEYWORDS["HAS_SYSTEM"]):
        add_relation("HAS_SYSTEM", grouped.get("Aircraft", []), grouped.get("System", []), 0.5)
    if sentence_contains(sentence, KEYWORDS["HAS_SUBSYSTEM"]):
        add_relation("HAS_SUBSYSTEM", grouped.get("System", []), grouped.get("Subsystem", []), 0.5)
    if sentence_contains(sentence, KEYWORDS["PART_OF"]):
        add_relation("PART_OF", grouped.get("Component", []) + grouped.get("Subsystem", []), grouped.get("System", []) + grouped.get("Aircraft", []), 0.6)
    if sentence_contains(sentence, KEYWORDS["APPLICABLE_TO"]):
        add_relation("APPLICABLE_TO", grouped.get("Procedure", []) + grouped.get("MaintenanceAction", []), grouped.get("Aircraft", []) + grouped.get("System", []) + grouped.get("Component", []), 0.6)
    if sentence_contains(sentence, KEYWORDS["USES_PROCEDURE"]):
        add_relation("USES_PROCEDURE", grouped.get("MaintenanceAction", []), grouped.get("Procedure", []), 0.6)
    if sentence_contains(sentence, KEYWORDS["REQUIRES_TOOL"]):
        add_relation("REQUIRES_TOOL", grouped.get("MaintenanceAction", []), grouped.get("Tool", []), 0.6)
    if sentence_contains(sentence, KEYWORDS["REQUIRES_MATERIAL"]):
        add_relation("REQUIRES_MATERIAL", grouped.get("MaintenanceAction", []), grouped.get("Material", []), 0.6)
    if sentence_contains(sentence, KEYWORDS["OCCURS_IN"]):
        add_relation("OCCURS_IN", grouped.get("FaultMode", []) + grouped.get("FaultSymptom", []), grouped.get("Component", []) + grouped.get("System", []) + grouped.get("Subsystem", []), 0.6)
    if sentence_contains(sentence, KEYWORDS["HAS_SOLUTION"]):
        add_relation("HAS_SOLUTION", grouped.get("FaultMode", []) + grouped.get("FaultCause", []) + grouped.get("FaultSymptom", []), grouped.get("MaintenanceAction", []), 0.6)
    if sentence_contains(sentence, KEYWORDS["AFFECTS"]):
        add_relation("AFFECTS", grouped.get("FaultMode", []) + grouped.get("FaultCause", []), grouped.get("Component", []) + grouped.get("System", []) + grouped.get("Subsystem", []), 0.5)
    if sentence_contains(sentence, KEYWORDS["MEASURED_BY"]):
        add_relation("MEASURED_BY", grouped.get("Component", []) + grouped.get("System", []) + grouped.get("Subsystem", []), grouped.get("Parameter", []), 0.5)

    if grouped.get("Aircraft") and grouped.get("System"):
        add_relation("HAS_SYSTEM", grouped.get("Aircraft", []), grouped.get("System", []), 0.4)
    if grouped.get("System") and grouped.get("Subsystem"):
        add_relation("HAS_SUBSYSTEM", grouped.get("System", []), grouped.get("Subsystem", []), 0.4)
    if (grouped.get("System") or grouped.get("Subsystem")) and grouped.get("Component"):
        add_relation("HAS_COMPONENT", grouped.get("System", []) + grouped.get("Subsystem", []), grouped.get("Component", []), 0.4)

    if grouped.get("Document"):
        documents = grouped.get("Document", [])
        others: List[dict] = []
        for entity_type, items in grouped.items():
            if entity_type == "Document":
                continue
            others.extend(items)
        add_relation("MENTIONED_IN", others, documents, 0.4)

    return relations


def run(clean_dir: Path, output_dir: Path) -> Path:
    sentence_path = clean_dir / SENTENCE_FILE
    entities_path = output_dir / "entities.jsonl"
    if not sentence_path.exists() or not entities_path.exists():
        raise SystemExit("Missing sentence or entity file. Run preprocess and entity extraction first.")

    entities_by_sentence: Dict[str, List[dict]] = defaultdict(list)
    for entity in iter_jsonl(entities_path):
        entities_by_sentence[entity["sentence_id"]].append(entity)

    relations: List[dict] = []
    for item in iter_jsonl(sentence_path):
        sentence_id = item["id"]
        sentence = item["sentence"]
        source_file = item.get("source_file", "")
        source_category = item.get("source_category", "")
        source_page_index = item.get("source_page_index")
        source_page_number = item.get("source_page_number")
        relations.extend(
            extract_relations(
                sentence,
                entities_by_sentence.get(sentence_id, []),
                source_file,
                source_category,
                sentence_id,
                source_page_index,
                source_page_number,
            )
        )

    output_path = output_dir / "relations.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as writer:
        for relation in relations:
            writer.write(json.dumps(relation, ensure_ascii=False) + "\n")

    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract relations from sentences and entities.")
    parser.add_argument("--clean", default=DEFAULT_CLEAN_DIR, help="Cleaned data directory")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="Output directory")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    output_path = run(Path(args.clean), Path(args.output))
    print(f"Relations saved to {output_path}")


if __name__ == "__main__":
    main()
