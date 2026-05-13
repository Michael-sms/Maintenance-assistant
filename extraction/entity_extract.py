from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List

DEFAULT_CLEAN_DIR = "data/cleaned"
DEFAULT_OUTPUT_DIR = "data/annotations"
DEFAULT_SCHEMA = "schema/entity_types.json"
SENTENCE_FILE = "sentences.jsonl"

PATTERN_MAP: Dict[str, List[str]] = {
    "Aircraft": [r"[\u4e00-\u9fffA-Za-z0-9-]{1,10}(?:飞行器|无人机|飞机|直升机)(?:型|号)?"],
    "System": [r"[\u4e00-\u9fffA-Za-z0-9-]{1,10}系统"],
    "Subsystem": [r"[\u4e00-\u9fffA-Za-z0-9-]{1,10}子系统"],
    "Component": [
        r"[\u4e00-\u9fffA-Za-z0-9-]{1,10}(?:部件|组件|装置|阀|泵|传感器|控制器|发动机|机翼|起落架|电池|电机)"
    ],
    "Material": [r"[\u4e00-\u9fffA-Za-z0-9-]{1,10}(?:材料|合金|胶|涂层)"],
    "Tool": [r"[\u4e00-\u9fffA-Za-z0-9-]{1,10}(?:工具|扳手|仪|仪器|设备)"],
    "Procedure": [r"[\u4e00-\u9fffA-Za-z0-9-]{1,12}(?:规程|流程|步骤|规范)"],
    "FaultSymptom": [r"[\u4e00-\u9fffA-Za-z0-9-]{1,12}(?:异常|失效|不足|过高|过低|泄漏|震动|噪声|超限|故障)"],
    "FaultCause": [r"由于([\u4e00-\u9fffA-Za-z0-9-]{1,12})", r"([\u4e00-\u9fffA-Za-z0-9-]{1,12})导致"],
    "FaultMode": [r"[\u4e00-\u9fffA-Za-z0-9-]{1,12}(?:故障模式|失效模式)"],
    "MaintenanceAction": [r"(?:更换|维修|检查|清洁|校准|调整|润滑|紧固)[\u4e00-\u9fffA-Za-z0-9-]{0,10}"],
    "Parameter": [r"[\u4e00-\u9fffA-Za-z0-9-]{1,12}(?:压力|温度|电压|电流|转速|流量|振动|噪声|位移)"],
    "Document": [r"[\u4e00-\u9fffA-Za-z0-9-]{1,12}(?:手册|说明书|规程|标准|规范)"],
}


def normalize_name(name: str) -> str:
    return re.sub(r"[\s\t]+", "", name)


def load_lexicon(lexicon_dir: Path) -> Dict[str, List[str]]:
    lexicon: Dict[str, List[str]] = defaultdict(list)
    if not lexicon_dir.exists():
        return lexicon
    for file_path in lexicon_dir.glob("*.txt"):
        entity_type = file_path.stem
        terms = [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if terms:
            lexicon[entity_type].extend(terms)
    return lexicon


def iter_sentences(sentence_path: Path) -> Iterable[dict]:
    with sentence_path.open("r", encoding="utf-8") as reader:
        for line in reader:
            if line.strip():
                yield json.loads(line)


def extract_entities(sentence: str, patterns: Dict[str, List[re.Pattern]], lexicon: Dict[str, List[str]]) -> List[dict]:
    entities: List[dict] = []
    for entity_type, regex_list in patterns.items():
        for regex in regex_list:
            for match in regex.finditer(sentence):
                name = match.group(1) if match.groups() else match.group(0)
                name = normalize_name(name)
                if len(name) < 2:
                    continue
                entities.append({"name": name, "type": entity_type, "mention": match.group(0)})
    for entity_type, terms in lexicon.items():
        for term in terms:
            if term and term in sentence:
                entities.append({"name": term, "type": entity_type, "mention": term})
    return entities


def build_patterns() -> Dict[str, List[re.Pattern]]:
    compiled: Dict[str, List[re.Pattern]] = {}
    for entity_type, pattern_list in PATTERN_MAP.items():
        compiled[entity_type] = [re.compile(pattern) for pattern in pattern_list]
    return compiled


def write_entities(entities: List[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as writer:
        for entity in entities:
            writer.write(json.dumps(entity, ensure_ascii=False) + "\n")


def run(clean_dir: Path, output_dir: Path, lexicon_dir: Path) -> Path:
    sentence_path = clean_dir / SENTENCE_FILE
    if not sentence_path.exists():
        raise SystemExit(f"Sentence file not found: {sentence_path}")

    patterns = build_patterns()
    lexicon = load_lexicon(lexicon_dir)
    records: List[dict] = []

    for item in iter_sentences(sentence_path):
        sentence = item["sentence"]
        extracted = extract_entities(sentence, patterns, lexicon)
        for entity in extracted:
            normalized = normalize_name(entity["name"])
            record = {
                "id": f"{entity['type']}::{normalized}",
                "name": normalized,
                "type": entity["type"],
                "mention": entity["mention"],
                "sentence_id": item["id"],
                "source_file": item["source_file"],
                "source_category": item.get("source_category", ""),
                "source_page_index": item.get("source_page_index"),
                "source_page_number": item.get("source_page_number"),
                "confidence": 0.6,
            }
            records.append(record)

    output_path = output_dir / "entities.jsonl"
    write_entities(records, output_path)
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract entities from sentences.")
    parser.add_argument("--clean", default=DEFAULT_CLEAN_DIR, help="Cleaned data directory")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--lexicon", default="extraction/lexicon", help="Optional lexicon directory")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    output_path = run(Path(args.clean), Path(args.output), Path(args.lexicon))
    print(f"Entities saved to {output_path}")


if __name__ == "__main__":
    main()
