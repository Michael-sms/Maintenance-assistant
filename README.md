# Maintenance-assistant

天津大学 2526 春季知识图谱课设项目：基于“知识图谱构建数据集”构建航空器领域知识图谱，并实现基础的抽取、入库与查询流程。

## 项目简介
- 项目应用名称：飞行器维修助手
- 应用场景：飞行器维修知识问答 + 典型故障定位辅助
- 目标：从三类数据（`变构飞行器/`、`飞行器/`、`维修类/`）自动抽取实体与关系，构建可查询的航空器维修知识图谱。
- 存储：Neo4j 图数据库（本地保留 CSV 作为入库备份）。

## 项目目录结构
```
final-project/
├─ README.md
├─ docx/                         # 课设文档
├─ 知识图谱构建数据集/             # 原始数据集
├─ data/
│  ├─ cleaned/                   # 清洗后文本
│  └─ annotations/               # 抽取结果（jsonl）
├─ extraction/                   # 抽取流水线
├─ graph/                        # CSV 导出 + Neo4j 入库/查询
├─ schema/                       # 本体与属性定义
└─ .env                          # 本地环境变量（不入库）
```

## 依赖安装（使用 uv）
```powershell
uv sync
```

## 快速开始
1) 运行抽取流水线
```powershell
python -m extraction.pipeline --input "知识图谱构建数据集" --data data
```

2) 统计概念与关系数量
```powershell
python -m extraction.count_stats --output data/annotations
```

3) 导出 Neo4j CSV（本地保留）
```powershell
python -m graph.export_csv --annotations data/annotations --output graph/csv
```

4) 导入 Neo4j
```powershell
python -m graph.import_neo4j --csv graph/csv
```

5) 查询示例
```powershell
python -m graph.query_api --name "燃油泵" --limit 10
```

## 技术栈
- Python 3.10+
- Neo4j 5.x
- pypdf（PDF 文本抽取）

## 当前进度
- 完成数据清洗与抽取流水线（规则/词典）
- 完成实体/关系统计脚本
- 完成 CSV 导出、Neo4j 入库与查询脚本
- 规划目标：实体 ≥ 500，关系 ≥ 1000

## 提 Issue
欢迎提 Issue 和交流建议。提交时请尽量提供：
- 复现步骤与命令
- 关键日志/错误栈
- 相关输入样例或文件路径

## 致谢
- 天津大学知识图谱课程
- Neo4j 社区与文档
