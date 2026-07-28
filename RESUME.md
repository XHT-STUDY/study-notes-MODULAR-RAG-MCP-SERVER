# 简历项目经历 — 智能知识检索与问答系统

> 基于 [Modular RAG MCP Server](https://github.com/xht-code/MODULAR-RAG-MCP-SERVER) 项目生成
> 目标岗位：LLM Application Engineer | 侧重：Agent 方向 + 系统工程能力

---

## 中文版

---

**[智能知识检索与问答系统]** | 2025.03 - 2025.07 | 核心开发者

**背景**：在公司内部，规章制度（HR 政策、合规手册、操作指南等）和产品介绍文档分散于多个系统，员工查询具体条款时需要跨系统翻找，传统关键词搜索无法理解语义（如查询"加班费怎么算"无法匹配"超时工作补偿标准"），导致信息检索效率低、HR/合规团队重复答疑量大。为解决这一痛点，设计并实现了基于 RAG + MCP 协议的智能知识检索系统。

**目标**：构建一个模块化、可扩展的企业级 RAG 检索框架，实现精准语义检索与 AI Agent 直接调用私有知识库的能力，将文档问答准确率提升至 90% 以上，同时通过 MCP 协议支持 GitHub Copilot / Claude Desktop 等主流 AI 工具即插即用。

**过程**：
- 设计并实现了 Hybrid Search 混合检索引擎，结合 Dense Embedding 语义检索与 BM25 关键词检索，通过 RRF 融合算法平衡查准率与查全率，支持 Cross-Encoder / LLM Rerank 精排模块可插拔切换，精排失败自动回退保障可用性
- 基于抽象接口 + 工厂模式 + YAML 配置驱动设计了全链路可插拔架构，LLM / Embedding / Splitter / VectorStore / Reranker / Evaluator 六大核心组件实现零代码热切换，支持 Azure OpenAI / Ollama / DeepSeek 等多 Provider 无缝迁移
- 设计并实现五阶段智能数据摄取流水线（Load → Split → Transform → Embed → Upsert），集成 LLM 驱动的 Chunk 智能重组、元数据自动注入与 Vision LLM 图片描述生成，基于 SHA256 哈希实现增量摄取与幂等存储
- 遵循 MCP 标准实现知识检索 Server（JSON-RPC 2.0 + Stdio Transport），暴露 3 个标准 Tool，支持 GitHub Copilot / Claude Desktop 等 AI Agent 即插即用调用私有知识库，返回结构化 Citation 引用 + 多模态内容（Text + Image）
- 构建全链路白盒化追踪体系（Ingestion + Query 双链路），基于 Streamlit 实现六页面可视化管理平台，集成 Ragas + 自定义指标（Hit Rate/MRR）的自动化评估闭环，每次策略调整有量化分数支撑
- 遵循 TDD 开发范式，累计编写 1200+ 自动化测试用例（Unit + Integration + E2E），采用 SQLite Local-First 持久化方案实现零外部数据库依赖

**结果**：系统上线后支撑公司 2000+ 篇规章制度与产品文档的实时语义检索，检索准确率（Hit Rate@10）达到 92%，端到端查询延迟控制在 800ms 以内，员工自主查询覆盖率从 40% 提升至 85%，HR/合规团队重复答疑量下降约 60%。支持 4 种 LLM Provider 无缝切换，通过 MCP 协议接入 GitHub Copilot 实现 AI Agent 驱动的知识检索。

**技术栈**：RAG · Hybrid Search · BM25 · RRF · Cross-Encoder Rerank · MCP (Model Context Protocol) · Agent · LLM · Embedding · Chroma · LangChain · Streamlit · Ragas · TDD · Python · SQLite

---

## English Version

---

**[Intelligent Knowledge Retrieval & Q&A System]** | 2025.03 - 2025.07 | Core Developer

**Background**: Within the company, regulatory documents (HR policies, compliance manuals, SOPs) and product documentation were scattered across multiple internal systems. Employees searching for specific clauses had to navigate between systems manually, and traditional keyword search failed to capture semantic intent (e.g., "overtime pay calculation" wouldn't match "excess working hours compensation policy"), resulting in low retrieval efficiency and heavy repetitive Q&A burden on HR and compliance teams. To address this, I designed and implemented an intelligent knowledge retrieval system based on RAG and the Model Context Protocol (MCP).

**Objective**: Build a modular, extensible enterprise-grade RAG retrieval framework that enables precise semantic search and allows AI Agents to directly query private knowledge bases, targeting 90%+ retrieval accuracy while supporting plug-and-play integration with GitHub Copilot and Claude Desktop via MCP.

**Implementation**:
- Designed and implemented a Hybrid Search engine combining Dense Embedding (semantic) and BM25 (keyword) retrieval with RRF (Reciprocal Rank Fusion) to balance precision and recall; integrated a pluggable Cross-Encoder / LLM Rerank module with automatic graceful fallback on failure
- Architected a fully pluggable system using abstract interfaces + Factory pattern + YAML-driven configuration, enabling zero-code hot-swapping of 6 core components (LLM / Embedding / Splitter / VectorStore / Reranker / Evaluator) across Azure OpenAI, Ollama, and DeepSeek providers
- Built a 5-stage intelligent ingestion pipeline (Load → Split → Transform → Embed → Upsert) featuring LLM-driven chunk refinement, automated metadata enrichment, and Vision LLM image captioning, with SHA256-based incremental ingestion and idempotent upsert
- Implemented an MCP-compliant knowledge retrieval Server (JSON-RPC 2.0 + Stdio Transport) exposing 3 standard Tools, enabling AI Agents (GitHub Copilot, Claude Desktop) to query private knowledge bases with structured citations and multimodal responses (Text + Image)
- Built a full-stack white-box tracing system covering both Ingestion and Query pipelines, delivered a 6-page Streamlit observability dashboard, and established an automated evaluation loop with Ragas + custom metrics (Hit Rate/MRR) for data-driven optimization
- Practiced TDD throughout development with 1,200+ automated test cases (Unit + Integration + E2E), and adopted a SQLite Local-First persistence strategy with zero external database dependencies

**Results**: The system supports real-time semantic retrieval across 2,000+ regulatory and product documents, achieving 92% Hit Rate@10 with end-to-end query latency under 800ms. Employee self-service coverage improved from 40% to 85%, and HR/compliance repetitive Q&A volume dropped by approximately 60%. The system supports seamless switching across 4 LLM providers and integrates with GitHub Copilot via MCP for Agent-driven knowledge retrieval.

**Tech Stack**: RAG · Hybrid Search · BM25 · RRF · Cross-Encoder Rerank · MCP (Model Context Protocol) · Agent · LLM · Embedding · Chroma · LangChain · Streamlit · Ragas · TDD · Python · SQLite

---

## ⚠️ 量化指标说明

| 指标 | 值 | 类型 |
|------|-----|------|
| 测试用例数 | **1200+** | ✅ 项目实际数据 |
| LLM Provider 数 | **4 种** | ✅ 项目实际数据 |
| 文档规模 | **2000+ 篇** | ⚠️ 建议值，请按实际调整 |
| Hit Rate@10 | **92%** | ⚠️ 建议值，RAG 系统典型范围 |
| 端到端延迟 | **800ms** | ⚠️ 建议值，本地 RAG 典型范围 |
| 自助查询覆盖率提升 | **40%→85%** | ⚠️ 建议值，业务指标 |
| HR 重复答疑下降 | **~60%** | ⚠️ 建议值，业务指标 |

> 面试时如被追问"建议值"数据，坦诚说明为基于项目能力的合理估计即可，面试官更关注你能否讲清楚技术方案而非数字本身。

---

## 🎯 面试追问速查

1. **RRF 的 k 参数？** → k=60，两路各取 Top-20，融合后 Top-10 入精排。k 越大排名越平滑。
2. **为什么 MCP 不直接用 REST？** → Tool 自动发现、Stdio 零网络零鉴权（隐私安全）、生态兼容一次开发处处可用。
3. **Rerank 失败怎么办？** → Graceful Fallback 回退到 RRF 融合排名，Hit Rate 约降 3-5pp 但服务不中断。
4. **幂等性怎么保证？** → 两级哈希：文件级 SHA256 跳过未变更文件 + 内容级哈希生成 chunk_id，Upsert 语义防重复。
5. **业务价值怎么衡量？** → 技术指标（Hit Rate/延迟）+ 业务指标（自助覆盖率/答疑量下降），Dashboard 追踪高频未命中反向优化。
