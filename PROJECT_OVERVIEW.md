# 项目说明（PROJECT OVERVIEW）

> 本文件是项目的**简明说明文档**：它是什么、为什么、架构怎么走。想动手跑起来，请看 [USAGE_GUIDE.md](USAGE_GUIDE.md)；想深入，文末有完整文档导航。

---

## 1. 一句话定位

**模块化、可观测的 RAG（检索增强生成）服务框架**，通过 **MCP（stdio 传输）** 向 AI 助手（GitHub Copilot / Claude / Cursor 等）暴露私有知识库检索工具。

- **性质**：面向**大模型岗位学习与面试求职**的实战项目，**非生产项目**（README 已声明不再积极扩展、不再修 Bug）。
- **价值点**：不是单点 demo，而是一整套工程化思路——DEV_SPEC 驱动开发、可插拔架构、三层测试、MCP 生态接入、可观测性。

## 2. 核心能力一览

| 模块 | 能力 | 关键位置 |
|---|---|---|
| **PDF 摄取管道** | PDF → Markdown → Chunk → Transform → Embedding → 入库；多模态图片自动生成描述并缝合进 Chunk | `src/ingestion/` |
| **混合检索** | Dense 向量 + BM25 稀疏 + RRF 融合 + 可选重排 | `src/core/query_engine/` |
| **MCP Server** | 标准 MCP（stdio）暴露 4 个工具，供 AI 客户端直接调用 | `src/mcp_server/` |
| **Streamlit 仪表盘** | 系统总览 / 数据浏览 / Ingestion 管理 / 摄取追踪 / 查询追踪 / 评估面板 | `src/observability/dashboard/` |
| **双评估体系** | Custom（规则式，零成本）+ Ragas；golden test set 回归 | `src/observability/evaluation/` |
| **全链路追踪** | Ingestion 与 Query 双链路白盒化，JSONL 落盘 | `src/core/trace/` |

## 3. 架构一图流

```
┌─ 客户端层 ──────────────────────────────────────────────┐
│  MCP Client（Copilot / Claude / Cursor）  │  Streamlit Dashboard │
└──────────────┬──────────────────────────────────────────┘
               │ JSON-RPC over stdio
┌─ MCP 接入层  src/mcp_server ─────────────┐
│  protocol_handler  →  tools/（4 个工具）            │
└──────────────┬──────────────────────────────────────────┘
┌─ 核心业务层  src/core ────────────────────┐
│  settings / types / query_engine / trace         │
└──────┬──────────────────┬──────────────────────────────┘
       │ 摄取                 │ 检索
┌─ 摄取  src/ingestion ─┐   ┌─ 可插拔组件  src/libs ──────┐
│ pipeline → chunking → │   │ BaseLLM / BaseEmbedding /        │
│ transform → embedding │   │ BaseReranker / BaseSplitter /    │
│ → storage              │   │ BaseVectorStore / BaseEvaluator  │
└──────┬──────────────────┘   └────────────────────────────────┘
       └──────── 存储：ChromaDB + BM25(JSON) + SQLite(历史) ────┘
```

**核心约定**：`src/libs/` 里的每个可插拔能力 = 一个 `Base*` ABC + 若干实现 + 一个 `XFactory` 注册表。**切换后端只需改 `config/settings.yaml` 的 `provider:` 字段，零代码修改**。

## 4. 摄取链路（6 阶段）

`src/ingestion/pipeline.py`：

1. **完整性检查**：SHA-256 查 SQLite 历史，跳过已处理文件（幂等）；
2. **加载**：`PdfLoader` 解析 PDF → `Document`，图片变为 `[IMAGE: {id}]` 占位符；
3. **分块**：`DocumentChunker` 生成确定性 chunk ID `{doc_id}_{index:04d}_{hash8}`；
4. **变换**：`ChunkRefiner` → `MetadataEnricher` → `ImageCaptioner`（规则版 + 可选 LLM 版，LLM 失败自动降级规则版）；
5. **编码**：`DenseEncoder`（嵌入 API）+ `SparseEncoder`（jieba 词频）；
6. **存储**：ChromaDB（内容哈希幂等）+ BM25 倒排索引 + ImageStorage(SQLite)。

## 5. 检索链路

`src/core/query_engine/`：

```
QueryProcessor（中文 jieba + 英文分词、停用词、key:value 过滤）
  → HybridSearch（并行 DenseRetriever + SparseRetriever）
  → RRFFusion（一条失败优雅回退另一条）
  → 可选 CoreReranker（失败返回原顺序 + used_fallback 标记）
  → ResponseBuilder（Markdown + [n] 引用 + 多模态 ImageContent）
```

- 数据契约集中在 `src/core/types.py`：`Document / Chunk / ChunkRecord / ProcessedQuery / RetrievalResult`。
- 每一步操作都建 `TraceContext`，经 `TraceCollector` 追加到 `logs/traces.jsonl`，仪表盘读取展示。

## 6. MCP 工具（4 个）

注册于 `src/mcp_server/protocol_handler.py`，模块在 `src/mcp_server/tools/`：

| 工具 | 功能 |
|---|---|
| `query_knowledge_hub` | 主检索工具：混合检索 → 融合 → 可选重排 → 可选答案，输出带引用 Markdown |
| `list_collections` | 列出所有集合及文档数 |
| `get_document_summary` | 按 doc_id 返回文档标题/摘要/标签/来源/块数 |
| `agent_query` | Agentic RAG（Phase 6）：`agent.enabled=false` 时降级为与 `query_knowledge_hub` 等价的直通检索 |

**默认配置注意**：`config/settings.yaml` 中 `agent.enabled: false`，即**默认只检索、不生成 LLM 答案**；回答走 `answer_generator.provider: "extractive"`（抽取式，无需 API key）。`BaseLLM` 仅用于重排与摄取变换（chunk 精炼、元数据增强、图片描述）。

## 7. 插件式切换与 None 降级

- **切换后端** = 只改 `config/settings.yaml` 的 `provider:` 字段（openai / azure / ollama / deepseek / qwen 等）。
- **None 降级**：`NoneReranker` / `NoneAnswerGenerator` / `NoneAgent` 让禁用功能短路，调用方无需分支判断。
- **无 key 也能跑**：dense 检索失败自动回退 sparse-only（BM25/jieba）；回答用 extractive；评估用 custom（规则式）。完整离线需要本地 Ollama 作为 embedding/LLM 后端。

## 8. 目录速查

```
src/libs/           可插拔提供方库（Base ABC + Factory + 实现）
src/core/           settings / types / query_engine / response / trace
src/ingestion/      pipeline / chunking / transform / embedding / storage
src/mcp_server/     protocol_handler + tools/
src/observability/  logger / dashboard / evaluation
scripts/            薄 CLI 入口（bootstrap / ingest / query / evaluate / ...）
config/             settings.yaml + .env（密钥，均 gitignore，用 .example 生成）
prompts/            版本化 Prompt 模板（frontmatter + checksum）
tests/              unit / integration / e2e + fixtures
```

## 9. 关键文档导航

| 文档 | 内容 | 何时看 |
|---|---|---|
| [USAGE_GUIDE.md](USAGE_GUIDE.md) | 全新环境配置 + 启动 + 测试 + 日常使用流程（本套文档的"动手篇"） | 拿到代码第一步 |
| [README.md](README.md) | 完整介绍、使用策略、FAQ、简历参考 | 想了解全貌 / 找"怎么用这个项目" |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 架构详解（目录、流程图、数据模型、测试体系附录） | 想深入理解设计 |
| [DEV_SPEC.md](DEV_SPEC.md) | 开发规格文档（设计 + 排期 + 测试策略 §4） | 想学习"如何用 Spec 驱动开发" |
| [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md) | Phase 0–6 逐步改造记录（真实数字） | 想了解项目演进史 |
| [ONBOARDING.md](ONBOARDING.md) | 全新 clone 实测手册（含实测记录） | 配置环境遇到问题 |
| [REPRODUCE.md](REPRODUCE.md) | 环境可复现指南 | CI / 可复现安装 |
| [CLAUDE.md](CLAUDE.md) | Claude Code 工作约定（命令 / 架构 / 已知问题） | 用 Claude Code 改代码时 |
