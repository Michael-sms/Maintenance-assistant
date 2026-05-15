from __future__ import annotations

import csv
import difflib
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from neo4j import GraphDatabase


UI_DIR = Path(__file__).resolve().parents[1] / "ui"
CSV_DIR = Path(__file__).resolve().parents[2] / "graph" / "csv"


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


def get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name) or default
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


class ParseRequest(BaseModel):
    input: str
    history: list[dict[str, str]] = []


class ExecuteRequest(BaseModel):
    skill: str
    params: dict[str, Any]


class ComposeRequest(BaseModel):
    input: str
    skill: str
    params: dict[str, Any]
    result: dict[str, Any]


class Neo4jClient:
    def __init__(self) -> None:
        uri = get_env("NEO4J_URI", "bolt://localhost:7687")
        user = get_env("NEO4J_USER", "neo4j")
        password = get_env("NEO4J_PASSWORD")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self.driver.close()

    def run(self, query: str, **params: Any) -> list[dict[str, Any]]:
        with self.driver.session() as session:
            records = session.run(query, **params)
            return [dict(record) for record in records]

    def fetch_relation_types(self) -> list[str]:
        query = "MATCH ()-[r]->() RETURN DISTINCT r.type AS type ORDER BY type"
        rows = self.run(query)
        return [row["type"] for row in rows if row.get("type")]

    def fetch_property_keys(self) -> list[str]:
        query = "CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey"
        rows = self.run(query)
        return [row["propertyKey"] for row in rows if row.get("propertyKey")]


def normalize_name(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def normalize_for_match(text: str) -> str:
    cleaned = re.sub(r"[\s,，。;；、/\\|]+", " ", text)
    cleaned = re.sub(r"[\(\)\[\]{}<>\"'“”‘’]+", "", cleaned)
    return normalize_name(cleaned).lower()


def build_bigrams(text: str) -> set[str]:
    if len(text) < 2:
        return {text} if text else set()
    return {text[i : i + 2] for i in range(len(text) - 1)}


def build_fault_candidates(text: str, max_rounds: int = 10) -> list[str]:
    normalized = normalize_name(text)
    if not normalized:
        return []

    strip_prefixes = ["故障", "异常", "失效", "报警", "排查", "原因", "现象", "问题", "查询", "检索"]
    cleaned = normalized
    for prefix in strip_prefixes:
        cleaned = cleaned.replace(prefix, " ")

    separators = r"[\s,，。;；、/\\|]+"
    raw_parts = [part.strip() for part in re.split(separators, cleaned) if part.strip()]

    synonyms = {
        "故障": ["异常", "失效", "报警", "问题"],
        "报警": ["告警"],
        "压力": ["压强"],
        "温度": ["温升"],
        "振动": ["震动"],
        "漏": ["泄漏", "渗漏"],
        "堵": ["堵塞", "阻塞"],
        "磨损": ["磨耗"],
        "卡滞": ["卡住", "阻滞"],
        "失效": ["故障", "异常"]
    }

    candidates: list[str] = []

    def add_candidate(value: str) -> None:
        value = normalize_name(value)
        if value and value not in candidates:
            candidates.append(value)

    add_candidate(normalized)
    add_candidate(cleaned)

    for part in raw_parts:
        add_candidate(part)
        for key, syns in synonyms.items():
            if key in part:
                for syn in syns:
                    add_candidate(part.replace(key, syn))

    if len(candidates) > max_rounds:
        candidates = candidates[:max_rounds]
    return candidates


def load_entity_index(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    items: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8") as reader:
        csv_reader = csv.DictReader(reader)
        for row in csv_reader:
            name = row.get("name") or ""
            entity_type = row.get("type") or ""
            name = normalize_name(name)
            if not name:
                continue
            items.append({"name": name, "type": entity_type})
    return items


def score_candidate(query: str, candidate: str) -> float:
    if not query or not candidate:
        return 0.0
    query_norm = normalize_for_match(query)
    candidate_norm = normalize_for_match(candidate)
    if not query_norm or not candidate_norm:
        return 0.0
    ratio = difflib.SequenceMatcher(None, query_norm, candidate_norm).ratio()
    bonus = 0.0
    if query_norm in candidate_norm or candidate_norm in query_norm:
        bonus += 0.2
    q_bi = build_bigrams(query_norm)
    c_bi = build_bigrams(candidate_norm)
    if q_bi and c_bi:
        overlap = len(q_bi & c_bi) / max(len(q_bi), 1)
        bonus += overlap * 0.3
    return ratio + bonus


def find_similar_entities(
    query: str,
    items: list[dict[str, str]],
    limit: int = 10,
    types: set[str] | None = None
) -> list[str]:
    scored: list[tuple[float, str]] = []
    for item in items:
        if types and item.get("type") not in types:
            continue
        candidate = item.get("name", "")
        score = score_candidate(query, candidate)
        if score <= 0:
            continue
        scored.append((score, candidate))
    scored.sort(key=lambda x: x[0], reverse=True)
    results: list[str] = []
    for _, name in scored:
        if name not in results:
            results.append(name)
        if len(results) >= limit:
            break
    return results


def heuristic_parse(text: str) -> dict[str, Any]:
    lowered = text.lower()
    if any(key in text for key in ["路径", "关系", "链路"]):
        parts = re.split(r"与|和|到|->|→", text)
        if len(parts) >= 2:
            return {
                "skill": "path_query",
                "params": {
                    "source": normalize_name(parts[0]),
                    "target": normalize_name(parts[1])
                }
            }
    if any(key in text for key in ["故障", "异常", "失效", "报警", "排查", "原因"]):
        return {"skill": "fault_investigation", "params": {"name": normalize_name(text)}}
    match = re.search(r"实体[:：](.+)", text)
    if match:
        return {"skill": "entity_lookup", "params": {"name": normalize_name(match.group(1))}}
    return {"skill": "entity_lookup", "params": {"name": normalize_name(text)}}


def call_deepseek(messages: list[dict[str, str]], temperature: float = 0.2) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8")
    parsed = json.loads(body)
    return parsed["choices"][0]["message"]["content"]


def try_parse_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def build_graph(records: list[dict[str, Any]]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []
    for row in records:
        source = row.get("source")
        target = row.get("target")
        relation = row.get("relation")
        if source:
            nodes.setdefault(source, {"id": source, "label": source, "type": row.get("source_type")})
        if target:
            nodes.setdefault(target, {"id": target, "label": target, "type": row.get("target_type")})
        if source and target and relation:
            links.append({"source": source, "target": target, "label": relation})
    return {"nodes": list(nodes.values()), "links": links}


def format_records(records: list[dict[str, Any]]) -> list[str]:
    lines = []
    for row in records:
        source = row.get("source")
        target = row.get("target")
        relation = row.get("relation")
        if source and target and relation:
            lines.append(f"{source} -[{relation}]-> {target}")
    return lines


def build_entity_query(include_aliases: bool) -> str:
    base = (
        "MATCH (n:Entity) "
        "WHERE toLower(n.name) CONTAINS toLower($name) "
    )
    if include_aliases:
        base += (
            "OR any(alias IN coalesce(n.aliases, []) "
            "WHERE toLower(alias) CONTAINS toLower($name)) "
        )
    base += (
        "WITH n LIMIT $node_limit "
        "OPTIONAL MATCH (n)-[r]-(m:Entity) "
        "RETURN n.name AS source, n.type AS source_type, r.type AS relation, "
        "m.name AS target, m.type AS target_type "
        "LIMIT $limit"
    )
    return base


def build_fault_query(include_aliases: bool) -> str:
    where_clause = "toLower(n.name) CONTAINS toLower($name)"
    if include_aliases:
        where_clause += (
            " OR any(alias IN coalesce(n.aliases, []) "
            "WHERE toLower(alias) CONTAINS toLower($name))"
        )
    query = (
        "MATCH (n:Entity) "
        f"WHERE {where_clause} "
        "WITH n, CASE WHEN n.type IN $fault_types THEN 0 ELSE 1 END AS rank "
        "ORDER BY rank "
        "LIMIT $node_limit "
        "OPTIONAL MATCH (n)-[r]-(m:Entity) "
        "RETURN n.name AS source, n.type AS source_type, r.type AS relation, "
        "m.name AS target, m.type AS target_type "
        "LIMIT $limit"
    )
    return query


def execute_entity_lookup(
    client: Neo4jClient,
    name: str,
    limit: int,
    include_aliases: bool
) -> dict[str, Any]:
    query = build_entity_query(include_aliases)
    records = client.run(query, name=name, node_limit=5, limit=limit)
    return {"records": records, "graph": build_graph(records)}


def execute_fault_investigation(
    client: Neo4jClient,
    name: str,
    limit: int,
    include_aliases: bool
) -> dict[str, Any]:
    query = build_fault_query(include_aliases)

    fault_types = ["部件", "FaultSymptom", "FaultCause", "FixMethod"]
    candidates = build_fault_candidates(name, max_rounds=10)
    last_records: list[dict[str, Any]] = []
    for candidate in candidates:
        records = client.run(
            query,
            name=candidate,
            node_limit=5,
            limit=limit,
            fault_types=fault_types
        )
        if records:
            return {
                "records": records,
                "graph": build_graph(records),
                "matched": candidate
            }
        last_records = records

    index = getattr(app.state, "entity_index", [])
    fallback_candidates = find_similar_entities(
        name,
        index,
        limit=10,
        types=set(fault_types)
    )
    for candidate in fallback_candidates:
        records = client.run(
            query,
            name=candidate,
            node_limit=5,
            limit=limit,
            fault_types=fault_types
        )
        if records:
            return {
                "records": records,
                "graph": build_graph(records),
                "matched": candidate,
                "fallback": True
            }

    if last_records:
        return {"records": last_records, "graph": build_graph(last_records)}

    raise HTTPException(
        status_code=404,
        detail="故障排查未命中结果，已扩展检索到最大轮次仍未找到。"
    )


def execute_path_query(client: Neo4jClient, source: str, target: str) -> dict[str, Any]:
    query = (
        "MATCH (a:Entity), (b:Entity) "
        "WHERE toLower(a.name) CONTAINS toLower($source) "
        "AND toLower(b.name) CONTAINS toLower($target) "
        "WITH a, b LIMIT 1 "
        "MATCH p=shortestPath((a)-[*..4]-(b)) "
        "RETURN p"
    )
    records = client.run(query, source=source, target=target)
    if not records:
        return {"records": [], "graph": {"nodes": [], "links": []}}

    path = records[0].get("p")
    if not path:
        return {"records": [], "graph": {"nodes": [], "links": []}}

    nodes: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []
    for rel in path.relationships:
        start = rel.start_node
        end = rel.end_node
        source = start.get("name")
        target_name = end.get("name")
        relation = rel.get("type")
        if source:
            nodes.setdefault(source, {"id": source, "label": source, "type": start.get("type")})
        if target_name:
            nodes.setdefault(
                target_name, {"id": target_name, "label": target_name, "type": end.get("type")}
            )
        if source and target_name:
            links.append({"source": source, "target": target_name, "label": relation or "关联"})

    records_list = []
    for link in links:
        records_list.append({
            "source": link["source"],
            "relation": link["label"],
            "target": link["target"]
        })

    return {"records": records_list, "graph": {"nodes": list(nodes.values()), "links": links}}


def compose_answer(input_text: str, skill: str, result: dict[str, Any]) -> dict[str, Any]:
    records = result.get("records", [])
    context_lines = format_records(records)
    if not os.getenv("DEEPSEEK_API_KEY"):
        highlights = context_lines[:3] if context_lines else ["暂无关联关系，可尝试更具体的部件或故障描述"]
        answer = "已完成知识图谱查询。" if records else "未找到相关关系，请尝试更具体的部件或故障描述。"
        return {"answer": answer, "highlights": highlights}

    prompt = (
        "你是飞行器维修助手，需要把图谱查询结果包装成自然语言答复。"
        "请输出 JSON，包含 answer 和 highlights（数组）。"
    )
    content = "\n".join(context_lines) or "无可用关系" 
    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": f"用户问题：{input_text}\n技能：{skill}\n关系：\n{content}"
        }
    ]
    try:
        raw = call_deepseek(messages)
        parsed = try_parse_json(raw)
        if parsed and "answer" in parsed:
            return {
                "answer": parsed.get("answer", ""),
                "highlights": parsed.get("highlights", [])
            }
    except Exception:
        pass

    highlights = context_lines[:3] if context_lines else ["暂无关联关系"]
    answer = "已完成知识图谱查询。" if records else "未找到相关关系，请尝试更具体的部件或故障描述。"
    return {"answer": answer, "highlights": highlights}


load_env_file(Path(".env"))
app = FastAPI()
neo4j_client: Neo4jClient | None = None


@app.on_event("startup")
def on_startup() -> None:
    global neo4j_client
    neo4j_client = Neo4jClient()
    app.state.relation_types = neo4j_client.fetch_relation_types()
    app.state.property_keys = neo4j_client.fetch_property_keys()
    csv_dir = Path(os.getenv("CSV_DIR", str(CSV_DIR)))
    app.state.entity_index = load_entity_index(csv_dir / "entities.csv")


@app.on_event("shutdown")
def on_shutdown() -> None:
    if neo4j_client:
        neo4j_client.close()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/skills/parse")
def parse_skill(request: ParseRequest) -> dict[str, Any]:
    if os.getenv("DEEPSEEK_API_KEY"):
        prompt = (
            "请根据用户输入，选择 skill：entity_lookup、fault_investigation 或 path_query。"
            "并输出 JSON：{\"skill\":..., \"params\":{...}}。"
            "path_query 需要 source 和 target。"
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": request.input}
        ]
        try:
            raw = call_deepseek(messages)
            parsed = try_parse_json(raw)
            if parsed and "skill" in parsed:
                return parsed
        except Exception:
            pass
    return heuristic_parse(request.input)


@app.post("/api/skills/execute")
def execute_skill(request: ExecuteRequest) -> dict[str, Any]:
    if not neo4j_client:
        raise HTTPException(status_code=500, detail="Neo4j client not initialized")

    skill = request.skill
    params = request.params or {}
    limit = int(params.get("limit", 30))

    include_aliases = "aliases" in getattr(app.state, "property_keys", [])

    if skill == "entity_lookup":
        name = params.get("name") or ""
        return execute_entity_lookup(neo4j_client, name, limit, include_aliases)
    if skill == "fault_investigation":
        name = params.get("name") or ""
        return execute_fault_investigation(neo4j_client, name, limit, include_aliases)
    if skill == "path_query":
        source = params.get("source") or ""
        target = params.get("target") or ""
        return execute_path_query(neo4j_client, source, target)

    return {"records": [], "graph": {"nodes": [], "links": []}}


@app.post("/api/skills/compose")
def compose_skill(request: ComposeRequest) -> dict[str, Any]:
    return compose_answer(request.input, request.skill, request.result)


app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")
