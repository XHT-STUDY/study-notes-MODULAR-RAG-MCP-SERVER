# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

模块化、可观测的 RAG（检索增强生成）服务框架，通过 **MCP（stdio 传输）** 向 AI 助手（Copilot / Claude 等）暴露私有知识库检索工具。核心能力：PDF 摄取管道、混合检索（稠密向量 + BM25 稀疏 + RRF 融合 + 可选重排）、Streamlit 仪表盘、Ragas 评估、全链路追踪。

- **定位**：学习 / 面试作品项目，**非生产项目**，README 声明不再积极扩展。
- **插件式架构**：LLM / Embedding / Reranker / Splitter / VectorStore / Evaluator 均可通过 `config/settings.yaml` 切换，无需改代码。
- **注意**：当前系统**仅检索、不生成 LLM 答案**（`BaseLLM` 只用于重排和摄取变换：chunk 精炼、元数据增强、图片描述）。

## 常用命令

先激活虚拟环境（Windows）：`.\.venv\Scripts\Activate.ps1`

```bash
# 安装（含 dev 依赖：pytest / ruff / mypy / openai）
pip install -e ".[dev]"

# 测试（markers: unit / integration / e2e / llm / slow；addopts -v --tb=short）
python -m pytest
python -m pytest -m "not llm"        # 排除真实 LLM 测试
python -m pytest tests/unit/test_config_loading.py -q        # 单文件
python -m pytest tests/unit/test_config_loading.py::test_load_settings_success -q  # 单用例

# Lint 与类型检查
ruff check src tests     # select E,F,I,N,W,UP，忽略 E501，line-length=100
mypy src

# 一键引导 / 环境自检 / 种子数据（Phase 1：Python 3.12 + uv.lock 可复现）
.\bootstrap.bat --seed             # 或 ./bootstrap.sh --seed：建 3.12 venv + uv sync --locked + 自检 + 摄取 sample 文档
python scripts/self_check.py       # 环境自检（9 项，全绿则退出码 0；--json 供 CI）
python scripts/seed_docs.py        # 幂等摄取 tests/fixtures/sample_documents/ 的 sample PDF（--clean 全量重建）
uv sync --locked                   # 严格按 uv.lock 安装（不要改动锁文件，除非更新依赖后重新 uv lock）

# 摄取 / 查询 / 评估 / 仪表盘
python scripts/ingest.py --path <pdf文件或目录> --collection <集合名> [--force] [--config <path>]
python scripts/query.py --query "问题" [--collection <集合名>] [--top-k 10] [--no-rerank] [--verbose]
python scripts/evaluate.py [--test-set path] [--collection <集合名>] [--top-k 10] [--json]
python scripts/start_dashboard.py --port 8501
```

**注意**：`main.py` 目前是 **stub**（只打印 "MCP Server will be implemented in Phase E"），`mcp-server` 控制台脚本也指向它，均未启动服务器。真正的 MCP 服务器入口是 `python src/mcp_server/server.py`。

## 架构概览

分层结构（`src/` 下按 `pyproject.toml` 的 wheel packages 打包）：

| 目录 | 职责 |
|---|---|
| `src/libs/` | **可插拔提供方库** —— Base ABC + Factory 注册表 + 具体实现 |
| `src/core/` | 业务逻辑 —— query_engine 检索栈、response 组装、settings、types、trace |
| `src/ingestion/` | 摄取编排 —— pipeline、chunking、transform、embedding、storage |
| `src/mcp_server/` | MCP 协议层 —— protocol_handler + tools/ |
| `src/observability/` | logger、Streamlit 仪表盘、evaluation |
| `scripts/` | 薄 CLI 入口 |

### 模块化核心：工厂注册模式

每个可插拔能力遵循同一套约定：

- 一个 `Base*` ABC（如 `BaseEmbedding.embed()`、`BaseVectorStore.upsert/query/get_by_ids()`、`BaseLLM.chat()`、`BaseReranker.rerank()`、`BaseEvaluator.evaluate()`）+ 若干具体实现。
- 一个 `XFactory`，持有 `_PROVIDERS: dict[str, type]`，提供 `register_provider() / create(settings, **override_kwargs) / list_providers()`。`create()` 用字典查找（无 if/elif 链），构造契约统一为 `provider_class(settings=..., **override_kwargs)`。
- **切换后端 = 只改 `config/settings.yaml` 的 `provider:` 字段**。
- 部分工厂不自注册：向量存储在 `src/libs/vector_store/__init__.py` 注册，LLM（文本 + 视觉分离）在 `src/libs/llm/__init__.py` 注册；嵌入在 `embedding_factory.py` 内自注册。Evaluator 工厂最复杂，支持 `_LAZY_PROVIDERS`（ragas/composite）+ `NoneEvaluator` 兜底。
- **None 降级**：`NoneReranker` / `NoneEvaluator` 让禁用功能短路，调用方无需分支判断。

### 摄取链路（6 阶段，`src/ingestion/pipeline.py`）

1. **完整性检查**：SHA-256（SQLite）跳过已处理文件
2. **加载**：`PdfLoader.load()` 解析 PDF → `Document`，图片变为 `[IMAGE: {image_id}]` 占位符
3. **分块**：`DocumentChunker` 生成确定性 chunk ID `{doc_id}_{index:04d}_{hash8}`
4. **变换**：`ChunkRefiner` → `MetadataEnricher` → `ImageCaptioner`（规则版 + 可选 LLM 版，LLM 失败自动降级规则版；提示词在 `config/prompts/*.txt`）
5. **编码**：`BatchProcessor` 配 `DenseEncoder`（嵌入 API）+ `SparseEncoder`（jieba 词频）
6. **存储**：`VectorUpserter` 写 ChromaDB（幂等、稳定内容哈希 ID）+ `BM25Indexer`（JSON 倒排索引，`data/db/bm25/{collection}/`）+ `ImageStorage`（SQLite）

### 检索链路（`src/core/query_engine/`）

`QueryProcessor`（中文 jieba + 英文分词、停用词、`key:value` 过滤解析）→ `HybridSearch` 并行跑 `DenseRetriever` + `SparseRetriever` → `RRFFusion` 融合（一条失败时优雅回退另一条）→ 可选 `CoreReranker`（失败返回原顺序 + `used_fallback`）→ `ResponseBuilder` 输出 Markdown + `[n]` 引用 + 多模态 `ImageContent`。

- **数据契约集中在 `src/core/types.py`**：`Document` / `Chunk` / `ChunkRecord` / `ProcessedQuery` / `RetrievalResult`，所有检索阶段共用。
- 追踪：每个操作建 `TraceContext`，经 `TraceCollector` 追加到 `logs/traces.jsonl`，仪表盘读取该文件 + 存储层展示。

### MCP 工具注册

`src/mcp_server/server.py` → `protocol_handler.py:create_mcp_server()` → `_register_default_tools()` 导入 `src/mcp_server/tools/*` 各模块，模块导出 `register_tool(protocol_handler)` 并声明 `TOOL_NAME` / `TOOL_DESCRIPTION` / `TOOL_INPUT_SCHEMA`（JSON Schema）+ async handler。现有 3 个工具：`query_knowledge_hub`（主检索工具，按集合懒加载）、`list_collections`、`get_document_summary`。

**MCP 服务器关键约定**：所有日志重定向到 stderr（stdout 保留给 JSON-RPC）；工具 handler 内阻塞 I/O 用 `asyncio.to_thread()`；重型 import（chromadb 等）在主线程预加载避免 import-lock 死锁。`query_knowledge_hub` 中 `SparseRetriever` 每次查询重载 BM25 索引，因此仪表盘摄取的数据无需重启服务器即可检索到。

## 已知问题与进行中改造

- **`gaizao_plan.md` 是当前改造方案（Phase 0–6，Phase 0–1 已完成，2–6 规划中），改代码前先读它**。已确认的问题：
  - 真实 API key 曾提交进 `config/settings.yaml` —— **Phase 0 已实施**（环境变量优先 + 模板化 + gitignore + 停止跟踪，见 `DEVELOPMENT_LOG.md`）；key 仍在 git 历史，需用户轮换。
  - 依赖 `>=` 无锁、环境不可复现 —— **Phase 1 已实施**（`.python-version` 3.12 + `uv.lock` + `scripts/bootstrap.py` + 一键引导，见 `DEVELOPMENT_LOG.md`）。全新环境：`.\bootstrap.bat --seed`。
  - `main.py` / `mcp-server` 控制台脚本是 stub（Phase E 内容缺失）。
  - `tests/fixtures/golden_test_set.json` 的 `expected_chunk_ids`/`expected_sources` 为空，导致 hit_rate/mrr 恒为 0。
  - BM25 `remove_document` 存在孤儿分块 bug（内容哈希与前缀不匹配）。
- 重要文档：`ARCHITECTURE.md`（架构详解）、`DEV_SPEC.md`（224KB 开发规范，含测试策略 §4）、`README.md`、`RESUME.md`。
- 无 CI 配置（计划 Phase 5 增加 GitHub Actions）。

## 扩展约定

- **新增提供方**：在对应 Factory 注册并设 `config/settings.yaml` 的 `provider:`；若该家族在 `__init__.py` 注册（vector_store / llm），则在包级注册。
- **新增 MCP 工具**：在 `src/mcp_server/tools/` 放模块，导出 `register_tool()`，并接入 `protocol_handler.py:_register_default_tools()`。
- 项目自带 9 个 Agent 技能（`.claude/skills/` 与 `.github/skills/` 镜像）：`setup`（环境配置）、`qa-tester`（串行 QA 流程，状态由 `qa_bootstrap.py`/`qa_config.py` 管理）、`auto-coder`（spec→code→test 驱动）、`package`（打包清理）等，是项目的既定开发流程。

## 开发日志约定

- **每次完成一个 Phase 的开发后**，向仓库根 `DEVELOPMENT_LOG.md` **顶部**（`---` 分隔线下方、`## Phase 0` 之前）追加一条结构化记录。
- 记录结构（以 `DEVELOPMENT_LOG.md` 头部的「条目模板」为准）：开发内容 / 测试方法 / 预期效果 / 改动原因 / 重点难点 / 应学到什么 / 验证结果。
- 语言用中文；验证结果要写**实际跑出的数字**（通过/失败数），不要只写"通过"。
