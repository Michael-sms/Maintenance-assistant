# Neo4j 入库与查询

本目录提供导出 CSV、导入 Neo4j 与基础查询脚本。导出的 CSV 会保留在 `graph/csv/`，以便本地存档。

## 1. 导出 CSV
```powershell
python -m graph.export_csv --annotations data/annotations --output graph/csv
```
导出结果包含：`entities.csv`、`relations.csv`、`triples.csv`。

## 2. 导入 Neo4j
建议使用 `.env` 保存连接信息，脚本会自动读取。
示例：
```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

```powershell
python -m graph.import_neo4j --csv graph/csv
```

## 3. 查询示例
```powershell
python -m graph.query_api --name "燃油泵" --limit 10
```
