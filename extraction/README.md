# 信息抽取流水线

本目录提供**文本清洗 → 分句 → 实体抽取 → 关系抽取 → 初步去重**的可运行流水线，输入默认来自 `知识图谱构建数据集/`，并保留来源目录类别字段（变构飞行器/飞行器/维修类）。支持 `.pdf` 文本抽取（依赖 `pypdf`），会过滤目录页/乱码行/元数据页，并保留页码字段。

## 目录
- `preprocess.py`：文本清洗与分句，生成 `data/cleaned/sentences.jsonl`
- `entity_extract.py`：基于规则/词典抽取实体，生成 `data/annotations/entities.jsonl`
- `relation_extract.py`：基于规则抽取关系，生成 `data/annotations/relations.jsonl`
- `fusion.py`：初步去重与融合，生成 `entities_dedup.jsonl` 与 `relations_dedup.jsonl`
- `pipeline.py`：一键执行全流程

## 快速运行（示例）
```powershell
python -m extraction.pipeline --demo
```

## 运行真实数据
```powershell
python -m extraction.pipeline --input "知识图谱构建数据集" --data data
```

## 统计概念与关系数量
```powershell
python -m extraction.count_stats --output data/annotations
```

## 扩展方式
- 词典扩展：在 `extraction/lexicon/` 下按实体类型放置 `Component.txt` 等文件。
- 规则扩展：在 `entity_extract.py` 与 `relation_extract.py` 的规则表中新增模式。
