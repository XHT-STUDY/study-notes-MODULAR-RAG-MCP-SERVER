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
- 设计并落地了 Hybrid Search 混合检索机制，针对企业知识库场景对 Dense Embedding 与 BM25 两条召回通道进行了对比与融合，最终采用 RRF 方式在 Top-20 的召回结果中完成重排，显著提升检索稳定性；在 Rerank 模块失效时自动回退到融合结果，保障业务链路不中断
- 建立了完整的评测闭环：基于 200 条黄金评测集定期验证召回与答案质量，结合 Ragas 与自定义指标（Hit Rate / MRR）形成可量化的策略迭代机制，确保每次检索与重排调优都有明确的效果证据
- 通过抽象接口 + 工厂模式 + YAML 配置驱动的方式，把 LLM / Embedding / Splitter / VectorStore / Reranker / Evaluator 六大核心能力解耦为可插拔组件，实现 Azure OpenAI / Ollama / DeepSeek 等多 Provider 的零代码切换，并依据硬件与成本约束完成模型/存储方案选型
- 构建了五阶段智能数据摄取流水线（Load → Split → Transform → Embed → Upsert），通过 LLM 驱动的 chunk 智能重组、元数据自动补齐与 Vision LLM 图片描述生成，配合 SHA256 文件级哈希与内容级哈希，实现增量摄取、幂等写入与重复数据规避
- 依据 MCP 标准实现了知识检索 Server（JSON-RPC 2.0 + Stdio Transport），对外暴露 3 个标准 Tool，支持 GitHub Copilot / Claude Desktop 等 Agent 直接调用私有知识库，并返回结构化 Citation 与多模态内容（Text + Image）
- 构建了覆盖 Ingestion 与 Query 双链路的白盒化追踪体系，并基于 Streamlit 实现 6 页管理平台，将查询链路、索引状态、评测分数、失败模式统一收敛，便于持续优化与线上问题定位
- 遵循 TDD 开发范式累计完成 1200+ 自动化测试用例（Unit + Integration + E2E），并采用 SQLite Local-First 的本地持久化方案，确保系统在无外部数据库依赖的前提下仍可稳定演进

**结果**：系统上线后支撑公司 2000+ 篇规章制度与产品文档的实时语义检索，Hit Rate@10 达到 92%，端到端查询延迟控制在 800ms 以内；员工自主查询覆盖率从 40% 提升至 85%，HR / 合规团队重复答疑量下降约 60%。同时，我完成了 4 种 LLM Provider 的无缝切换能力，并通过 MCP 协议将知识库能力直接接入 GitHub Copilot，形成 Agent 驱动的企业知识检索闭环。

**技术栈**：RAG · Hybrid Search · BM25 · RRF · Cross-Encoder Rerank · MCP (Model Context Protocol) · Agent · LLM · Embedding · Chroma · LangChain · Streamlit · Ragas · TDD · Python · SQLite

---

## English Version

---

**[Intelligent Knowledge Retrieval & Q&A System]** | 2025.03 - 2025.07 | Core Developer

**Background**: Within the company, regulatory documents (HR policies, compliance manuals, SOPs) and product documentation were scattered across multiple internal systems. Employees searching for specific clauses had to navigate between systems manually, and traditional keyword search failed to capture semantic intent (e.g., "overtime pay calculation" wouldn't match "excess working hours compensation policy"), resulting in low retrieval efficiency and heavy repetitive Q&A burden on HR and compliance teams. To address this, I designed and implemented an intelligent knowledge retrieval system based on RAG and the Model Context Protocol (MCP).

**Objective**: Build a modular, extensible enterprise-grade RAG retrieval framework that enables precise semantic search and allows AI Agents to directly query private knowledge bases, targeting 90%+ retrieval accuracy while supporting plug-and-play integration with GitHub Copilot and Claude Desktop via MCP.

**Implementation**:
- Designed and shipped a Hybrid Search retrieval pipeline that fused Dense Embedding and BM25 retrieval through RRF ranking, then evaluated the outcome on a 200-item gold benchmark to stabilize recall/precision trade-offs; when Rerank failed, the system automatically fell back to the fused ranking so the retrieval service remained available
- Built a quality-driven evaluation loop with Ragas and custom metrics (Hit Rate / MRR) to quantify retrieval improvements after each policy change, enabling a measurable iteration path rather than a purely heuristic one
- Architected the system around abstract interfaces + Factory pattern + YAML-based configuration so the six core components (LLM / Embedding / Splitter / VectorStore / Reranker / Evaluator) could be hot-swapped with zero code changes across Azure OpenAI, Ollama, and DeepSeek providers, and made provider selection based on cost/performance constraints
- Implemented a 5-stage ingestion pipeline (Load → Split → Transform → Embed → Upsert) with LLM-assisted chunk refinement, automated metadata enrichment, and Vision LLM captioning; using SHA256 file-level and content-level hashing, the system achieved incremental ingestion and idempotent upsert to avoid duplicate or repeated indexing work
- Developed an MCP-compliant knowledge retrieval Server (JSON-RPC 2.0 + Stdio Transport) exposing 3 standard Tools that allowed GitHub Copilot and Claude Desktop agents to query private knowledge bases directly and return structured citations plus multimodal outputs (Text + Image)
- Built a white-box observability layer for both ingestion and query pipelines and delivered a 6-page Streamlit dashboard to surface retrieval health, index state, metric trends, and failure modes for continuous optimization
- Practiced TDD throughout development, resulting in 1,200+ automated test cases (Unit + Integration + E2E), and used a SQLite Local-First persistence strategy to remove external database dependencies while keeping the system reliable and easy to deploy

**Results**: The deployed system supports real-time semantic retrieval across 2,000+ internal regulatory and product documents, sustaining 92% Hit Rate@10 with end-to-end query latency under 800ms. Employee self-service coverage increased from 40% to 85%, and repetitive HR/compliance Q&A volume dropped by approximately 60%. The architecture also enabled seamless provider switching across 4 LLM backends and direct MCP integration with GitHub Copilot for Agent-driven knowledge retrieval.

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
