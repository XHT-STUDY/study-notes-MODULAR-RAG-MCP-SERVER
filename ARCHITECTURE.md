# Modular RAG MCP Server — 项目架构与流程说明

> 版本：1.0 | 基于 commit `2ed4b8d` | 2026-07-28

---

## 目录

1. [项目总览](#1-项目总览)
2. [目录结构总览](#2-目录结构总览)
3. [系统架构全景图](#3-系统架构全景图)
4. [核心流程详解](#4-核心流程详解)
   - [4.1 数据摄取流程 (Ingestion Pipeline)](#41-数据摄取流程-ingestion-pipeline)
   - [4.2 检索查询流程 (Query Pipeline)](#42-检索查询流程-query-pipeline)
   - [4.3 MCP 协议交互流程](#43-mcp-协议交互流程)
5. [可插拔架构设计](#5-可插拔架构设计)
6. [可观测性体系](#6-可观测性体系)
7. [数据模型](#7-数据模型)
8. [入口与脚本](#8-入口与脚本)

---

## 1. 项目总览

**Modular RAG MCP Server** 是一个**可插拔、可观测的模块化 RAG（检索增强生成）服务框架**，通过 **MCP（Model Context Protocol）** 协议对外暴露标准化工具接口，支持 GitHub Copilot、Claude Desktop 等 AI 助手直接调用私有知识库进行检索问答。

### 核心能力一览

| 模块 | 能力 | 说明 |
|------|------|------|
| **Ingestion Pipeline** | PDF → Markdown → Chunk → Transform → Embedding → Upsert | 全链路数据摄取，支持多模态图片描述（Image Captioning） |
| **Hybrid Search** | Dense (向量) + Sparse (BM25) + RRF Fusion + Rerank | 粗排召回 + 精排重排的两段式检索架构 |
| **MCP Server** | 标准 MCP 协议暴露 Tools | `query_knowledge_hub`、`list_collections`、`get_document_summary` |
| **Dashboard** | Streamlit 六页面管理平台 | 系统总览 / 数据浏览 / Ingestion 管理 / 摄取追踪 / 查询追踪 / 评估面板 |
| **Evaluation** | Ragas + Custom 评估体系 | 支持 golden test set 回归测试，拒绝"凭感觉"调优 |
| **Observability** | 全链路白盒化追踪 | Ingestion 与 Query 两条链路的每一个中间状态透明可见 |

### 技术亮点

- **全链路可插拔架构**：LLM / Embedding / Reranker / Splitter / VectorStore / Evaluator 每个环节均定义了抽象接口，通过 `settings.yaml` 一键切换后端
- **混合检索 + 重排**：BM25 稀疏检索 (精确匹配) + Dense Embedding (语义匹配) → RRF 融合 → Cross-Encoder / LLM Rerank 精排
- **多模态图像处理**：Image-to-Text 策略，Vision LLM 生成图片描述嵌入 Chunk，复用纯文本 RAG 链路
- **MCP 协议集成**：遵循 Model Context Protocol 标准，Stdio Transport 零网络端口部署
- **三层测试体系**：Unit / Integration / E2E，覆盖 1200+ 测试用例

---

## 2. 目录结构总览

```
MODULAR-RAG-MCP-SERVER/
│
├── main.py                          # 🔰 框架入口：加载配置 + 初始化日志
├── pyproject.toml                   # 项目元数据、依赖、pytest/ruff/mypy 配置
├── README.md                        # 项目 README（中英文）
├── DEV_SPEC.md                      # 开发规格文档（~3200 行，架构设计 + 排期）
│
├── config/                          # ⚙️ 配置层
│   ├── settings.yaml                #   主配置文件（LLM/Embedding/VectorStore/检索/评估等）
│   ├── test_credentials.yaml.example
│   └── prompts/                     #   LLM Prompt 模板
│       ├── chunk_refinement.txt     #     Chunk 精炼 Prompt
│       ├── image_captioning.txt     #     图片描述生成 Prompt
│       ├── metadata_enrichment.txt  #     元数据增强 Prompt
│       └── rerank.txt              #     LLM 重排序 Prompt
│
├── src/                             # 📦 主源码目录
│   ├── core/                        # 🧠 核心层（类型定义、配置、检索引擎、响应构建、链路追踪）
│   │   ├── settings.py              #   Settings 数据类 + YAML 加载器 + 校验器
│   │   ├── types.py                 #   核心数据类型（Document/Chunk/ChunkRecord/RetrievalResult 等）
│   │   ├── query_engine/            #   检索引擎
│   │   │   ├── query_processor.py   #     查询预处理（关键词提取、过滤器解析）
│   │   │   ├── dense_retriever.py   #     稠密检索（向量相似度）
│   │   │   ├── sparse_retriever.py  #     稀疏检索（BM25 关键词）
│   │   │   ├── hybrid_search.py     #     混合检索引擎（编排 Dense+Sparse+RRF）
│   │   │   ├── fusion.py            #     RRF 融合算法
│   │   │   └── reranker.py          #     核心重排序接口
│   │   ├── response/                #   响应构建
│   │   │   ├── response_builder.py  #     检索结果 → 格式化响应
│   │   │   ├── citation_generator.py#     引用标注生成
│   │   │   └── multimodal_assembler.py #  多模态内容组装（文字+图片）
│   │   └── trace/                   #   链路追踪
│   │       ├── trace_context.py     #     TraceContext 追踪上下文
│   │       └── trace_collector.py   #     Trace 收集与持久化
│   │
│   ├── ingestion/                   # 📥 数据摄取层
│   │   ├── pipeline.py              #   IngestionPipeline 编排器（6 阶段协调）
│   │   ├── document_manager.py      #   文档生命周期管理（跨存储 CRUD）
│   │   ├── chunking/
│   │   │   └── document_chunker.py  #     文档切块（LangChain RecursiveSplitter）
│   │   ├── embedding/
│   │   │   ├── dense_encoder.py     #     稠密向量编码
│   │   │   └── sparse_encoder.py    #     稀疏向量编码（BM25）
│   │   ├── transform/
│   │   │   ├── base_transform.py    #     Transform 抽象基类
│   │   │   ├── chunk_refiner.py     #     Chunk 精炼（去噪、合并、LLM 重组）
│   │   │   ├── metadata_enricher.py #     元数据增强（标题/摘要/标签生成）
│   │   │   └── image_captioner.py   #     图片描述生成（Vision LLM）
│   │   └── storage/
│   │       ├── vector_upserter.py   #     ChromaDB 向量写入
│   │       ├── bm25_indexer.py      #     BM25 倒排索引构建
│   │       └── image_storage.py     #     图片文件存储与索引
│   │
│   ├── libs/                        # 🔌 可插拔组件库（工厂模式 + 抽象基类）
│   │   ├── llm/                     #   LLM 提供者
│   │   │   ├── base_llm.py          #     BaseLLM 抽象基类
│   │   │   ├── base_vision_llm.py   #     BaseVisionLLM 抽象基类
│   │   │   ├── llm_factory.py       #     LLMFactory（文本 + 视觉双注册表）
│   │   │   ├── openai_llm.py / openai_vision_llm.py
│   │   │   ├── azure_llm.py / azure_vision_llm.py
│   │   │   ├── deepseek_llm.py
│   │   │   ├── ollama_llm.py
│   │   │   └── qwen_llm.py / qwen_vision_llm.py
│   │   ├── embedding/               #   Embedding 提供者
│   │   │   ├── base_embedding.py    #     BaseEmbedding 抽象基类
│   │   │   ├── embedding_factory.py #     EmbeddingFactory
│   │   │   ├── openai_embedding.py / azure_embedding.py
│   │   │   ├── ollama_embedding.py / qwen_embedding.py
│   │   ├── reranker/                #   重排序提供者
│   │   │   ├── base_reranker.py     #     BaseReranker（含 NoneReranker 空对象回退）
│   │   │   ├── reranker_factory.py  #     RerankerFactory
│   │   │   ├── cross_encoder_reranker.py
│   │   │   └── llm_reranker.py
│   │   ├── splitter/                #   文档切分器
│   │   │   ├── base_splitter.py     #     BaseSplitter 抽象基类
│   │   │   ├── splitter_factory.py  #     SplitterFactory
│   │   │   └── recursive_splitter.py#     LangChain RecursiveCharacterTextSplitter
│   │   ├── vector_store/            #   向量数据库
│   │   │   ├── base_vector_store.py #     BaseVectorStore 抽象基类
│   │   │   ├── vector_store_factory.py#   VectorStoreFactory
│   │   │   └── chroma_store.py      #     ChromaDB 实现
│   │   ├── loader/                  #   文档加载器
│   │   │   ├── base_loader.py       #     BaseLoader 抽象基类
│   │   │   ├── pdf_loader.py        #     MarkItDown PDF 加载器
│   │   │   └── file_integrity.py    #     SHA256 文件完整性检查
│   │   └── evaluator/               #   评估框架
│   │       ├── base_evaluator.py    #     BaseEvaluator 抽象基类
│   │       ├── evaluator_factory.py #     EvaluatorFactory
│   │       └── custom_evaluator.py  #     自定义评估器
│   │
│   ├── mcp_server/                  # 📡 MCP 协议服务层
│   │   ├── server.py                #   MCP Server 启动（Stdio Transport）
│   │   ├── protocol_handler.py      #   协议处理器（Tool 注册 + JSON-RPC 路由）
│   │   └── tools/                   #   MCP Tools 实现
│   │       ├── query_knowledge_hub.py  # 主检索工具（HybridSearch + Rerank）
│   │       ├── list_collections.py     # 列出可用集合
│   │       └── get_document_summary.py # 获取文档摘要
│   │
│   └── observability/               # 📊 可观测性层
│       ├── logger.py                #   结构化日志 + Trace 写入
│       ├── evaluation/              #   评估执行
│       │   ├── eval_runner.py       #     评估运行器
│       │   ├── ragas_evaluator.py   #     Ragas 评估集成
│       │   └── composite_evaluator.py#   组合评估器
│       └── dashboard/               #   Streamlit 管理平台
│           ├── app.py               #     多页面入口（6 页导航）
│           ├── pages/
│           │   ├── overview.py      #       系统总览（组件配置 + 数据统计）
│           │   ├── data_browser.py  #       数据浏览器（文档/Chunk/图片浏览）
│           │   ├── ingestion_manager.py#    Ingestion 管理（上传+删除+进度）
│           │   ├── ingestion_traces.py#     摄取追踪（阶段耗时瀑布图）
│           │   ├── query_traces.py  #       查询追踪（Dense/Sparse 对比 + Rerank 前后）
│           │   └── evaluation_panel.py#     评估面板（指标展示 + 历史趋势）
│           └── services/
│               ├── config_service.py#      配置读取服务
│               ├── data_service.py #       数据浏览服务
│               └── trace_service.py#       Trace 数据解析服务
│
├── scripts/                         # 🖥️ CLI 入口脚本
│   ├── ingest.py                    #   离线文档摄取
│   ├── query.py                     #   命令行查询测试
│   ├── evaluate.py                  #   评估执行
│   └── start_dashboard.py           #   Dashboard 启动器
│
├── tests/                           # 🧪 测试套件
│   ├── conftest.py                  #   pytest 共享 fixtures
│   ├── unit/                        #   单元测试（46 个文件）
│   ├── integration/                 #   集成测试（12 个文件）
│   ├── e2e/                         #   端到端测试（4 个文件）
│   └── fixtures/                    #   测试数据（样本 PDF、golden test set 等）
│
├── data/                            # 💾 运行时数据
│   └── db/
│       ├── chroma/                  #   ChromaDB 持久化向量库
│       ├── bm25/                    #   BM25 倒排索引（JSON）
│       ├── image_index.db           #   图片索引（SQLite）
│       └── ingestion_history.db     #   摄取历史（SQLite）
│
└── logs/                            # 📝 日志与 Trace
    └── traces.jsonl                 #   JSON Lines 格式的 Trace 记录
```

---

## 3. 系统架构全景图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MCP Clients                                       │
│         GitHub Copilot  │  Claude Desktop  │  Cursor  │  ...                │
└──────────────────────────┬──────────────────────────────────────────────────┘
                           │  JSON-RPC 2.0 over Stdio
                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────── MCP SERVER LAYER ────────────────────────────────┐│
│  │  server.py                     protocol_handler.py                      ││
│  │  ┌───────────────────────┐    ┌──────────────────────────────────────┐  ││
│  │  │ Stdio Transport       │───▶│ ProtocolHandler                      │  ││
│  │  │ (read_stream/write)   │    │  ├─ tools/list  → get_tool_schemas() │  ││
│  │  │                       │    │  └─ tools/call  → execute_tool()     │  ││
│  │  └───────────────────────┘    └───────────┬──────────────────────────┘  ││
│  │                                           │                              ││
│  │              ┌────────────────────────────┼──────────────────────────┐   ││
│  │              │          MCP TOOLS         │                          │   ││
│  │              │  ┌─────────────────────────▼───────────────────────┐  │   ││
│  │              │  │ query_knowledge_hub  │ list_collections         │  │   ││
│  │              │  │ get_document_summary │                          │  │   ││
│  │              │  └───────────────────────┬─────────────────────────┘  │   ││
│  │              └──────────────────────────┼────────────────────────────┘   ││
│  └─────────────────────────────────────────┼────────────────────────────────┘│
└─────────────────────────────────────────────┼────────────────────────────────┘
                                              │
           ┌──────────────────────────────────┼──────────────────────────────┐
           │                    CORE LAYER    │                              │
           │                                  ▼                              │
           │  ┌───────────────────────────────────────────────────────────┐  │
           │  │                   QUERY ENGINE                             │  │
           │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │  │
           │  │  │ Dense        │  │ Sparse       │  │ Reranker     │     │  │
           │  │  │ Retriever    │  │ Retriever    │  │ (CrossEnc/   │     │  │
           │  │  │ (Vector DB)  │  │ (BM25 Index) │  │  LLM/None)   │     │  │
           │  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │  │
           │  │         └──────────┬──────┘                 │             │  │
           │  │                    ▼                        │             │  │
           │  │         ┌──────────────────┐                │             │  │
           │  │         │  RRF Fusion      │                │             │  │
           │  │         │  (混合排序)       │────────────────┘             │  │
           │  │         └────────┬─────────┘                              │  │
           │  │                  ▼                                         │  │
           │  │         ┌──────────────────┐                               │  │
           │  │         │  Response Builder│                               │  │
           │  │         │  (引用+多模态)    │                               │  │
           │  │         └──────────────────┘                               │  │
           │  └───────────────────────────────────────────────────────────┘  │
           │                                                                 │
           │  ┌───────────────────────────────────────────────────────────┐  │
           │  │                 INGESTION PIPELINE                         │  │
           │  │                                                           │  │
           │  │  ① File Integrity → ② Load → ③ Chunk → ④ Transform      │  │
           │  │  (SHA256 跳过)    (PDF→MD)  (语义切块)  (精炼+增强+Caption)│  │
           │  │                                                           │  │
           │  │                          → ⑤ Embed → ⑥ Upsert            │  │
           │  │                        (Dense+Sparse) (向量+BM25+图片)    │  │
           │  └───────────────────────────────────────────────────────────┘  │
           │                                                                 │
           │  ┌───────────────────────────────────────────────────────────┐  │
           │  │                    DATA TYPES (types.py)                   │  │
           │  │   Document  →  Chunk  →  ChunkRecord  →  RetrievalResult  │  │
           │  └───────────────────────────────────────────────────────────┘  │
           └─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                       PLUGGABLE LIBS LAYER                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │   LLM    │ │Embedding │ │ Reranker │ │ Splitter │ │VectorStore│          │
│  │  (5 impl)│ │ (4 impl) │ │ (2 impl) │ │ (1 impl) │ │ (1 impl) │          │
│  │  OpenAI  │ │  OpenAI  │ │ CrossEnc │ │Recursive │ │ ChromaDB │          │
│  │  Azure   │ │  Azure   │ │ LLM-based│ │          │ │          │          │
│  │ DeepSeek │ │  Ollama  │ │          │ │          │ │          │          │
│  │  Ollama  │ │  Qwen    │ │          │ │          │ │          │          │
│  │  Qwen    │ │          │ │          │ │          │ │          │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│  ┌──────────┐ ┌──────────┐                                                  │
│  │  Loader  │ │Evaluator │   All use: BaseClass + Factory + settings.yaml   │
│  │  (1 impl)│ │ (2 impl) │                                                  │
│  │   PDF    │ │  Ragas   │                                                  │
│  │          │ │  Custom  │                                                  │
│  └──────────┘ └──────────┘                                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                     OBSERVABILITY LAYER                                      │
│  ┌──────────────────────────┐  ┌──────────────────────────────────────┐    │
│  │   TraceContext + Logger  │  │  Streamlit Dashboard (6 pages)       │    │
│  │   ┌──────────────────┐   │  │  Overview │ Data Browser             │    │
│  │   │ traces.jsonl     │───▶│  │ Ingestion Manager │ Traces ×2      │    │
│  │   │ (JSON Lines)     │   │  │ Evaluation Panel                    │    │
│  │   └──────────────────┘   │  └──────────────────────────────────────┘    │
│  └──────────────────────────┘                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 核心流程详解

### 4.1 数据摄取流程 (Ingestion Pipeline)

数据摄取是将原始文档（PDF）转化为可检索的向量化知识的过程。整个流程由 `IngestionPipeline` 类（[src/ingestion/pipeline.py](src/ingestion/pipeline.py)）编排，共 6 个阶段：

```
                      ┌────────────────────────────────────────────┐
                      │        INGESTION PIPELINE (6 Stages)        │
                      └────────────────────────────────────────────┘

  原始 PDF ──▶ ① File Integrity ──▶ ② Load ──▶ ③ Chunk ──▶ ④ Transform ──▶ ⑤ Embed ──▶ ⑥ Upsert
               │                    │           │             │               │             │
               │ SHA256 计算        │ MarkItDown│ LangChain   │ ┌─Refiner     │ ┌─Dense     │ ┌─ChromaDB
               │ 查 ingestion_      │ PDF→MD    │ Recursive   │ ├─Enricher    │ │  (API)    │ ├─BM25 Index
               │ history.db         │ 图片提取  │ TextSplitter│ └─Captioner   │ └─Sparse    │ └─ImageStore
               │                    │           │             │               │   (本地)    │
               │ 已有? → SKIP       │ Document  │ Chunk[]     │ Chunk[]       │ ChunkRecord[]│
               └────────────────────┴───────────┴─────────────┴───────────────┴─────────────┘
```

#### 各阶段详解

**① File Integrity Check（文件完整性检查）**
- **组件**: `SQLiteIntegrityChecker` ([src/libs/loader/file_integrity.py](src/libs/loader/file_integrity.py))
- **流程**: 计算原始 PDF 的 SHA256 → 查询 `data/db/ingestion_history.db` → 若 `status=success` 则跳过
- **数据表**:
  ```sql
  CREATE TABLE ingestion_history (
      file_hash TEXT PRIMARY KEY,
      file_path TEXT NOT NULL,
      file_size INTEGER,
      status TEXT NOT NULL CHECK(status IN ('success','failed','processing')),
      processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      error_msg TEXT,
      chunk_count INTEGER
  );
  ```

**② Load（文档加载）**
- **组件**: `PdfLoader` ([src/libs/loader/pdf_loader.py](src/libs/loader/pdf_loader.py))
- **工具**: MarkItDown（PDF → Markdown）
- **输出**: `Document` 对象 (`id`, `text` (Markdown), `metadata`)
  - `metadata.source_path`: 原始文件路径
  - `metadata.images`: 图片引用列表 `[{id, path, page, text_offset, text_length}]`
  - 图片占位符: `[IMAGE: {image_id}]` 已嵌入 Markdown 文本中
- **图片提取**: 提取的图片保存至 `data/images/{collection}/{image_id}.png`

**③ Chunk（文档切块）**
- **组件**: `DocumentChunker` ([src/ingestion/chunking/document_chunker.py](src/ingestion/chunking/document_chunker.py))
- **策略**: LangChain `RecursiveCharacterTextSplitter`，基于 Markdown 结构切分
- **参数**（来自配置）: `chunk_size=1000`, `chunk_overlap=200`
- **输出**: `Chunk[]`，每个 Chunk 带有 `text`, `metadata`, `start_offset`, `end_offset`, `source_ref`
  - 图片引用标记保持在对应的 Chunk 中

**④ Transform（转换增强）**
三个子步骤依次执行：

| 子步骤 | 组件 | 功能 | LLM 依赖 |
|--------|------|------|----------|
| **Chunk Refiner** | `ChunkRefiner` | 合并不完整段落、去除噪声、LLM 语义重组 | 可选 (use_llm) |
| **Metadata Enricher** | `MetadataEnricher` | 生成 `title`/`summary`/`tags` 注入 metadata | 可选 (use_llm) |
| **Image Captioner** | `ImageCaptioner` | 调用 Vision LLM 生成图片自然语言描述，注入 `metadata.image_captions` | Vision LLM |

- **设计**: 每个 Transform 实现 `BaseTransform` 接口 ([src/ingestion/transform/base_transform.py](src/ingestion/transform/base_transform.py))
- **幂等性**: 相同内容的 Chunk 产生相同结果
- **降级**: LLM 不可用时自动跳过，不阻塞管线

**⑤ Embed（向量编码）**
- **组件**: `BatchProcessor` + `DenseEncoder` + `SparseEncoder` ([src/ingestion/embedding/](src/ingestion/embedding/))
- **双路编码**:
  - **Dense Vector**: 调用 Embedding API (如 Qwen text-embedding-v3, 1024 维)，捕获语义
  - **Sparse Vector**: 本地计算 BM25 词频统计，捕获关键词
- **批处理**: 按 `batch_size=10` 批量调用 API
- **差量计算**: 内容哈希相同的 Chunk 复用已有向量，降低 API 成本

**⑥ Upsert（索引存储）**
- **组件**: `VectorUpserter` + `BM25Indexer` + `ImageStorage` ([src/ingestion/storage/](src/ingestion/storage/))
- **三路存储**:
  - **ChromaDB**: Dense Vector + 完整 Chunk 文本 + Metadata（`data/db/chroma/`）
  - **BM25 Index**: 倒排索引 JSON 文件（`data/db/bm25/{collection}/`）
  - **Image Storage**: 图片文件 + SQLite 索引表（`data/db/image_index.db`）
- **幂等**: `chunk_id = hash(source_path + section_path + content_hash)`，Upsert 语义

---

### 4.2 检索查询流程 (Query Pipeline)

检索流程采用**多阶段过滤架构**，由 `HybridSearch` 类（[src/core/query_engine/hybrid_search.py](src/core/query_engine/hybrid_search.py)）编排：

```
 用户查询: "如何配置 Azure OpenAI？"
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│ ① Query Processing (QueryProcessor)                          │
│    - 提取关键词: ["配置", "Azure", "OpenAI"]                    │
│    - 解析过滤器: {collection: "docs"}                         │
│    - 输出: ProcessedQuery                                     │
└──────────────────────┬───────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
┌──────────────────┐    ┌──────────────────────┐
│ ②a Dense Route   │    │ ②b Sparse Route      │
│ (DenseRetriever) │    │ (SparseRetriever)    │
│                  │    │                      │
│ Query→Embedding  │    │ 关键词→BM25 检索     │
│ →ChromaDB       │    │ →BM25 Index          │
│ Cosine Sim       │    │                      │
│ Top-20 candidates│    │ Top-20 candidates    │
└────────┬─────────┘    └──────────┬───────────┘
         │                         │
         │   ThreadPoolExecutor    │   ← 并行执行
         │   (max_workers=2)       │
         └────────────┬────────────┘
                      ▼
┌──────────────────────────────────────────────────────────────┐
│ ③ RRF Fusion (RRFFusion)                                     │
│    Score = 1/(k + Rank_dense) + 1/(k + Rank_sparse)          │
│    k = 60（来自配置 retrieval.rrf_k）                           │
│    → 输出 Top-10 融合结果                                      │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ ④ Rerank（可选，当前默认关闭）                                   │
│    ┌─ None: 直接返回 RRF 结果                                   │
│    ├─ Cross-Encoder: 本地模型逐对打分                            │
│    └─ LLM Rerank: LLM 对候选排序                                │
│    失败时 → Fallback 到 RRF 排序结果                             │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ ⑤ Response Building (ResponseBuilder)                         │
│    - 格式化 Markdown 文本 + 引用标注 [1],[2]...                  │
│    - 关联图片 → Base64 编码嵌入 ImageContent                    │
│    - 输出: MCPToolResponse (text + citations + images)         │
└──────────────────────────────────────────────────────────────┘
```

#### 容错降级机制

HybridSearch 实现了完整的降级策略：
- **Dense 失败** → 仅使用 Sparse 结果
- **Sparse 失败** → 仅使用 Dense 结果
- **两路均失败** → 抛出 RuntimeError
- **两路均返回空** → 返回空列表
- **Reranker 失败/超时** → 自动回退到 RRF 排序结果

---

### 4.3 MCP 协议交互流程

MCP Server 基于官方 Python MCP SDK 实现，采用 **Stdio Transport** 模式：

```
┌────────────┐                              ┌──────────────────────────────┐
│ MCP Client │  JSON-RPC 2.0 over stdin/out │       MCP Server              │
│ (Copilot)  │◄─────────────────────────────│       (Python 进程)            │
└────────────┘                              └──────────────────────────────┘
                                                    │
                                            ① 启动时注册 3 个 Tool
                                                    │
             ──── initialize ──────────────────────▶│
             ◀─── capabilities (tools: {}) ────────│
                                                    │
             ──── tools/list ──────────────────────▶│  ② ProtocolHandler
             ◀─── [Tool, Tool, Tool] ──────────────│     .get_tool_schemas()
                                                    │
             ──── tools/call ──────────────────────▶│  ③ ProtocolHandler
             │   {name: "query_knowledge_hub",      │     .execute_tool()
             │    arguments: {query: "...", ...}}    │         │
             │                                      │         ▼
             │                                      │    async handler(**args)
             │                                      │         │
             │                                      │         ▼
             │                                      │    QueryKnowledgeHubTool
             │                                      │    .execute()
             │                                      │         │
             │                                      │         ├─ HybridSearch
             │                                      │         ├─ Rerank
             │                                      │         └─ ResponseBuilder
             │                                      │
             ◀─── CallToolResult ──────────────────│
                  {content: [TextContent,           │
                             ImageContent],         │
                   isError: false}                  │
```

#### Tool 注册链

```
server.py:run_stdio_server_async()
  └─▶ create_mcp_server(name, version)
        └─▶ ProtocolHandler(server_name, server_version)
              └─▶ _register_default_tools(protocol_handler)
                    ├─▶ query_knowledge_hub.register_tool(handler)
                    ├─▶ list_collections.register_tool(handler)
                    └─▶ get_document_summary.register_tool(handler)
```

#### 三个 MCP Tool

| Tool 名称 | 输入参数 | 功能 |
|-----------|---------|------|
| `query_knowledge_hub` | `query` (必填), `top_k` (默认5), `collection` (可选) | 执行混合检索 + 重排，返回带引用的格式化结果 |
| `list_collections` | 无 | 列出所有可用知识库集合及其文档数量 |
| `get_document_summary` | `doc_id` (必填) | 获取指定文档的标题、摘要、元信息 |

---

## 5. 可插拔架构设计

### 设计原则

- **接口隔离**: 每个组件定义最小化的抽象基类（ABC），上层只依赖接口
- **配置驱动**: `settings.yaml` 指定各组件后端，零代码修改切换
- **工厂模式**: `Factory.create(settings)` → 根据配置动态实例化
- **优雅降级**: 首选不可用时自动回退（如 Reranker → None, Vision LLM → Skip）

### 组件架构

```
settings.yaml
     │
     ▼
┌──────────────────────────────────────────────────────┐
│                   FACTORY LAYER                       │
│                                                      │
│  LLMFactory.create(settings)                         │
│  ├─ provider="openai"  → OpenaiLLM(BaseLLM)          │
│  ├─ provider="azure"   → AzureLLM(BaseLLM)           │
│  ├─ provider="deepseek"→ DeepSeekLLM(BaseLLM)        │
│  ├─ provider="ollama"  → OllamaLLM(BaseLLM)          │
│  └─ provider="qwen"    → QwenLLM(BaseLLM)            │
│                                                      │
│  EmbeddingFactory.create(settings)                   │
│  ├─ provider="openai"  → OpenAIEmbedding             │
│  ├─ provider="azure"   → AzureEmbedding              │
│  ├─ provider="ollama"  → OllamaEmbedding             │
│  └─ provider="qwen"    → QwenEmbedding               │
│                                                      │
│  RerankerFactory.create(settings)                    │
│  ├─ provider="none"         → NoneReranker           │
│  ├─ provider="cross_encoder"→ CrossEncoderReranker   │
│  └─ provider="llm"          → LLMReranker            │
│                                                      │
│  VectorStoreFactory.create(settings)                 │
│  └─ provider="chroma"  → ChromaStore(BaseVectorStore)│
│                                                      │
│  SplitterFactory.create(settings)                    │
│  └─ splitter="recursive" → RecursiveSplitter         │
│                                                      │
│  EvaluatorFactory.create(settings)                   │
│  ├─ provider="ragas"   → RagasEvaluator              │
│  └─ provider="custom"  → CustomEvaluator             │
└──────────────────────────────────────────────────────┘
```

### 如何新增 Provider

1. 创建实现类，继承对应抽象基类（如 `BaseLLM`）
2. 在对应 `__init__.py` 中调用 `Factory.register_provider("name", ImplClass)`
3. 在 `settings.yaml` 中设置 `provider: "name"`
4. **无需修改任何业务代码**

---

## 6. 可观测性体系

### 追踪机制

系统通过 **TraceContext**（[src/core/trace/trace_context.py](src/core/trace/trace_context.py)）实现全链路白盒化追踪：

```
RAG Pipeline / MCP Tool
     │
     ▼
TraceContext(trace_type="query"|"ingestion")
     │
     ├─ .record_stage("dense_retrieval", {...}, elapsed_ms=...)
     ├─ .record_stage("fusion", {...}, elapsed_ms=...)
     ├─ .record_stage("rerank", {...}, elapsed_ms=...)
     └─ .finish()
           │
           ▼
TraceCollector.collect(trace)
           │
           ▼
logs/traces.jsonl  (JSON Lines 格式，每行一个完整 Trace)
           │
           ▼
Dashboard (TraceService 解析 → 页面可视化)
```

### 两类 Trace

**Ingestion Trace**: 记录一次文档摄取的完整过程
```
trace_id | trace_type="ingestion" | timestamp | source_path | collection
  stages:
    load     → method/markitdown | text_length | image_count | elapsed_ms
    split    → method/recursive  | chunk_count | avg_chunk_size | elapsed_ms
    transform→ refined_by_llm/rule | enriched_by_llm/rule | captioned_chunks | elapsed_ms
    embed    → dense_dim/dense_count | sparse_doc_count | elapsed_ms
    upsert   → dense_store/chroma | sparse_store/bm25 | image_store | elapsed_ms
```

**Query Trace**: 记录一次查询的完整过程
```
trace_id | trace_type="query" | timestamp | user_query | collection
  stages:
    query_processing → method | keywords | elapsed_ms
    dense_retrieval  → provider | top_k | result_count | chunks[] | elapsed_ms
    sparse_retrieval → method/bm25 | keyword_count | result_count | chunks[] | elapsed_ms
    fusion           → method/rrf | input_lists | result_count | elapsed_ms
    rerank           → provider | top_k | used_fallback | elapsed_ms
```

### Dashboard 六页面

| 页面 | 数据源 | 功能 |
|------|--------|------|
| **Overview** | Settings + DocumentManager | 组件配置、数据资产统计、系统健康 |
| **Data Browser** | ChromaStore + ImageStorage | 文档/Chunk/图片浏览与搜索 |
| **Ingestion Manager** | IngestionPipeline + DocumentManager | 文件上传、实时进度条、删除 |
| **Ingestion Traces** | traces.jsonl | 摄取历史、阶段耗时瀑布图 |
| **Query Traces** | traces.jsonl | 查询历史、Dense/Sparse 对比、Rerank 变化 |
| **Evaluation Panel** | Evaluator | 运行评估、指标对比、历史趋势 |

---

## 7. 数据模型

核心数据类型定义在 [src/core/types.py](src/core/types.py)，贯穿整个管线：

```
                          INGESTION FLOW                          QUERY FLOW
                          ══════════════                          ══════════

  PDF ──▶ Document ──▶ Chunk[] ──▶ ChunkRecord[]             Raw Query ──▶ ProcessedQuery
           │             │            │                                     │
           │ id          │ id         │ id                                  │ original_query
           │ text (MD)   │ text       │ text                                │ keywords[]
           │ metadata    │ metadata   │ metadata (enriched)                 │ filters{}
           │   .images[] │   .chunk_  │   .title/.summary/.tags/.captions   │ expanded_terms[]
           │             │    index   │ dense_vector[]                      │
           │             │   .start_  │ sparse_vector{}                     │
           │             │    offset  │                                      │
           │             │   .end_    │                                      │
           │             │    offset  │                                      │
           │             │   .source_ │                                      │
           │             │    ref     │                                      │
           │             │            │                                      │
           ▼             ▼            ▼                                      ▼
        Loader  ◀──  Splitter  ◀──  Embedder              ┌─────────────────────┐
        (PDF→MD)     (语义切块)     (Dense+Sparse)         │  RetrievalResult     │
                                                           │  ├─ chunk_id        │
                                                           │  ├─ score           │
                                                           │  ├─ text            │
                                                           │  └─ metadata        │
                                                           └─────────────────────┘
```

### 类型转换链路

```
Ingestion:  PDF → Document → Chunk → ChunkRecord → (VectorStore + BM25 Index)
                    ↑           ↑           ↑
               PdfLoader  DocumentChunker  BatchProcessor

Query:    Raw Query → ProcessedQuery → RetrievalResult[] → MCPToolResponse
                         ↑                  ↑                  ↑
                    QueryProcessor   HybridSearch+RRF   ResponseBuilder
```

---

## 8. 入口与脚本

### 8.1 框架入口 — `main.py`

```
main.py
  └─ main() → int
       ├─ load_settings("config/settings.yaml")
       ├─ get_logger(log_level=settings.observability.log_level)
       └─ return 0（MCP Server 由 src/mcp_server/server.py 独立启动）
```

当前 `main.py` 仅做配置加载和日志初始化，MCP Server 的实际启动入口在 `src/mcp_server/server.py`。

### 8.2 MCP Server 启动

```
src/mcp_server/server.py
  └─ main() → int
       └─ run_stdio_server()
            └─ asyncio.run(run_stdio_server_async())
                 ├─ _redirect_all_loggers_to_stderr()  # stdout 仅输出 JSON-RPC
                 ├─ _preload_heavy_imports()           # 主线程预加载 chromadb 等重依赖
                 ├─ create_mcp_server(name, version)   # 注册 3 个 MCP Tool
                 └─ stdio_server() → server.run()      # 开始监听 stdin/stdout
```

### 8.3 CLI 脚本

| 脚本 | 用途 | 示例 |
|------|------|------|
| `scripts/ingest.py` | 离线摄取 PDF 到知识库 | `python scripts/ingest.py -p docs/report.pdf -c contracts` |
| `scripts/query.py` | 命令行查询测试 | `python scripts/query.py "如何配置 Azure？"` |
| `scripts/evaluate.py` | 运行 RAG 评估 | `python scripts/evaluate.py --test-set golden_test_set.json` |
| `scripts/start_dashboard.py` | 启动 Streamlit Dashboard | `python scripts/start_dashboard.py` 或 `streamlit run src/observability/dashboard/app.py` |

### 8.4 配置管理

配置经由 `src/core/settings.py` 的统一加载链路：

```
config/settings.yaml
     │
     ▼
yaml.safe_load()
     │
     ▼
Settings.from_dict(data)   ← 基于 frozen dataclass 的强类型校验
     ├─ LLMSettings         (provider, model, temperature, max_tokens, api_key, base_url...)
     ├─ EmbeddingSettings   (provider, model, dimensions, api_key, base_url...)
     ├─ VisionLLMSettings   (enabled, provider, model, max_image_size, api_key...)
     ├─ VectorStoreSettings (provider, persist_directory, collection_name)
     ├─ RetrievalSettings   (dense_top_k, sparse_top_k, fusion_top_k, rrf_k)
     ├─ RerankSettings      (enabled, provider, model, top_k)
     ├─ EvaluationSettings  (enabled, provider, metrics[])
     ├─ ObservabilitySettings(log_level, trace_enabled, trace_file, structured_logging)
     └─ IngestionSettings   (chunk_size, chunk_overlap, splitter, batch_size, chunk_refiner, metadata_enricher)
     │
     ▼
validate_settings()  ← 必填字段校验
     │
     ▼
load_settings(path) → Settings  ← 对外唯一入口
```

---

## 附录：测试体系

```
tests/
├── unit/          (46 文件)  快速无外部依赖测试
├── integration/   (12 文件)  需要实际组件（ChromaDB, LLM API 等）
├── e2e/           (4 文件)   完整端到端流程测试
└── fixtures/                 测试数据和样本文档
```

- **框架**: pytest + pytest-cov + pytest-asyncio + pytest-mock
- **标记**: `unit`, `integration`, `e2e`, `llm`, `slow`
- **运行**: `pytest -m "not llm"` 跳过需要 API 的测试
