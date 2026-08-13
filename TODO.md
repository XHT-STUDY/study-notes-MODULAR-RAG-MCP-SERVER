# Modular RAG MCP Server 项目伴读 TODO

> 目标：从“能运行项目”逐步达到“能解释架构、追踪关键调用链、判断设计取舍、定位问题并独立扩展”，并积累一套可重组为正式学习笔记的素材。
>
> 开始日期：2026-08-12  
> 当前阶段：第 1.2 节（离线摄取主链）  
> 最近更新：2026-08-12

## 使用约定

- `[ ]` 未开始，`[~]` 进行中，`[x]` 已完成，`[!]` 有待复查。
- 每次只推进一个小节；默认每小节 30～60 分钟，可按理解情况继续拆分。
- 每节固定经过：概念定位 → 代码入口 → 调用链 → 动手验证 → 复述题 → 笔记素材。
- 每节问题分三层：基础理解题 → 代码追问题 → 面试场景题；重点章节再加入故障诊断与设计取舍追问。
- 面试题不仅检查结论，还练习回答结构：背景/问题 → 项目做法 → 原因与取舍 → 风险/改进 → 验证证据。
- 对回答进行面试式反馈：指出正确点、缺失点、表述风险，并给出一版更凝练的参考话术；参考话术用于校准，不要求死记。
- 只有能够不看答案完成“本节验收”，才把小节标记为完成。
- 伴读时以当前代码和测试为事实依据，以架构文档解释设计，以开发日志理解演进；三者不一致时保留差异并调查原因。
- 每次伴读结束后更新本文的“当前阶段”“章节进度”和“伴读记录”。

## 最终学习成果

- [ ] 用一张图讲清客户端、MCP、Agent、检索、摄取、存储、评估、Dashboard 的关系。
- [ ] 独立讲清一份 PDF 从文件到可检索 Chunk 的完整生命周期。
- [ ] 独立讲清一次查询从输入到带引用、多模态回答的完整生命周期。
- [ ] 解释 Dense、BM25、RRF、Rerank 各自解决的问题及其组合理由。
- [ ] 解释项目如何通过抽象基类、Factory、配置和空对象实现可插拔与降级。
- [ ] 解释 MCP stdio 的协议边界、工具注册、参数校验和响应结构。
- [ ] 解释 Agentic RAG 相比直接检索新增的路由、工具循环、记忆、反思和降级。
- [ ] 能使用 Trace、Dashboard、评估集和分层测试诊断质量或工程问题。
- [ ] 独立完成一个小型扩展，并用测试和 Trace 证明它工作正确。
- [ ] 将伴读产出重组为一份结构完整的项目学习笔记。

## 总进度

| 章 | 主题 | 预计小节 | 状态 |
|---|---|---:|---|
| 0 | 建立基线与学习地图 | 2 | [x] |
| 1 | 项目全景与两条主链路 | 3 | [~] |
| 2 | 启动入口与配置系统 | 3 | [ ] |
| 3 | 核心数据契约 | 3 | [ ] |
| 4 | 可插拔组件层 | 4 | [ ] |
| 5 | 数据摄取流水线 | 6 | [ ] |
| 6 | 混合检索流水线 | 6 | [ ] |
| 7 | 回答、引用与多模态响应 | 3 | [ ] |
| 8 | MCP 服务与工具边界 | 4 | [ ] |
| 9 | Agentic RAG | 5 | [ ] |
| 10 | 文档生命周期与数据版本 | 4 | [ ] |
| 11 | 可观测性与 Dashboard | 4 | [ ] |
| 12 | 评估、测试与质量闭环 | 5 | [ ] |
| 13 | 工程演进、文档漂移与设计取舍 | 3 | [ ] |
| 14 | 综合实战与学习笔记收口 | 4 | [ ] |

## 第 0 章：建立基线与学习地图

### 0.1 仓库盘点

- [x] 确认项目定位：模块化、多模态、可观测的 RAG MCP Server。
- [x] 确认技术栈：Python 3.12、MCP 1.x、ChromaDB、BM25/jieba、Streamlit、Ragas、pytest。
- [x] 统计规模：`src/` 126 个 Python 文件、约 24k 行；`tests/` 108 个 Python 文件、约 28k 行。
- [x] 确认主模块：`core`、`ingestion`、`libs`、`mcp_server`、`observability`。
- [x] 确认当前分支 `main` 与工作区初始状态干净。

### 0.2 运行基线

- [x] 运行 `scripts/self_check.py`：9/9 PASS。
- [x] 运行核心契约代表测试：ProtocolHandler、核心类型、RRF，共 78 passed。
- [!] 配置测试中依赖 `tmp_path` 的 8 项受当前 pytest 临时目录权限影响；其余代表测试 49 passed。后续测试章节复查，不暂判为业务代码失败。
- [x] 发现文档漂移样例：旧架构文档列出 3 个 MCP Tool，当前注册链已有第 4 个 `agent_query`。

## 第 1 章：项目全景与两条主链路

### 1.1 先建立最小心智模型

- [x] 区分 RAG 的离线摄取链与在线查询链。
- [ ] 区分框架主干与四类外部边界：模型服务、持久化存储、MCP Client、Dashboard 用户。
- [x] 解释为什么项目同时需要 `src/core`、`src/libs` 和 `src/ingestion`，而不是都放进一个 pipeline。
- [!] 画出不超过 12 个节点的项目全景图。（2026-08-12 主动跳过，后续有空补做）

本节必读：

- `README.md`：项目定位和能力清单。
- `ARCHITECTURE.md`：全景架构、摄取流程、查询流程。
- `pyproject.toml`：运行时依赖和入口定义。

本节验收：不看资料，用 3 分钟向他人说明“这个项目解决什么问题、数据如何进来、问题如何得到答案”。

### 1.2 离线摄取主链

伴读拆分：

- [x] 1.2.1 CLI 入口：参数解析、文件发现、Pipeline 装配与逐文件执行。
- [x] 1.2.2 Pipeline 六阶段：每阶段的输入、输出和错误边界。
- [x] 1.2.3 多存储落点：Chroma、BM25、SQLite 与图片目录。
- [~] 1.2.4 幂等与更新：`force`、SHA256、版本记录与清理。

- [x] 从 `scripts/ingest.py` 找到 `IngestionPipeline`。
- [x] 追踪 File Integrity → Load → Chunk → Transform → Encode → Store。
- [x] 识别 Chroma、BM25、SQLite、图片目录分别保存什么。
- [ ] 理解幂等摄取与强制重建的区别。

本节验收：给定一个 PDF，能按顺序说出每个阶段的输入、输出和失败时的影响。

### 1.3 在线查询主链

- [ ] 从 `query_knowledge_hub` 找到 Hybrid Search、Rerank、Answer Generator、Response Builder。
- [ ] 区分直接检索 `query_knowledge_hub` 与 Agent 查询 `agent_query`。
- [ ] 找到引用和图片内容进入 MCP 响应的位置。
- [ ] 对照 Trace 识别一次查询的阶段记录。

本节验收：能解释“用户问题如何最终变成 MCP content blocks”，并指出检索失败、重排失败、生成失败的降级位置。

## 第 2 章：启动入口与配置系统

### 2.1 启动入口

- [ ] 阅读 `main.py` 的 fail-fast 与延迟导入。
- [ ] 阅读 `src/mcp_server/server.py` 的 stdio 启动与 stdout/stderr 隔离。
- [ ] 对比 `python main.py`、`python -m src.mcp_server.server`、`mcp-server` 三种入口。

### 2.2 配置建模与加载

- [ ] 阅读 `src/core/settings.py` 中各 Settings 数据类。
- [ ] 追踪 YAML → `.env` → 进程环境变量的覆盖顺序。
- [ ] 理解必填字段、可选模块、类型转换和跨字段校验。
- [ ] 理解 `resolve_path()` 为什么以项目根为基准。

### 2.3 配置驱动与密钥治理

- [ ] 对照 `config/settings.yaml.example` 找到每个配置块的消费者。
- [ ] 区分功能开关、Provider 选择、凭据与路径配置。
- [ ] 验证敏感信息不应进入 Git 跟踪文件。

本章验收：给出一个配置字段，能找到其加载、校验、消费和环境变量覆盖的完整路径。

## 第 3 章：核心数据契约

### 3.1 摄取数据模型

- [ ] 阅读 `Document`、`Chunk`、`ChunkRecord`。
- [ ] 比较三者字段、生命周期和转换关系。
- [ ] 理解 `source_path`、稳定 Chunk ID、offset、metadata 的不变量。

### 3.2 查询数据模型

- [ ] 阅读 `ProcessedQuery` 与 `RetrievalResult`。
- [ ] 理解不同检索器为何必须返回统一结果契约。
- [ ] 识别 score 的语义在不同阶段如何变化。

### 3.3 响应与 Agent 数据模型

- [ ] 阅读 `Citation`、`MCPToolResponse`、`AgentResult`、`Message`、`ToolCall`。
- [ ] 画出核心类型转换链。
- [ ] 用核心类型单测验证必要不变量。

本章验收：能从类型层面解释各模块为何可以低耦合协作。

## 第 4 章：可插拔组件层

### 4.1 抽象基类与契约

- [ ] 阅读 LLM、Embedding、Splitter、VectorStore、Reranker、Evaluator 的 Base 类。
- [ ] 归纳同步/异步、输入/输出、异常约定。

### 4.2 Factory 与 Provider 注册

- [ ] 追踪 `provider` 字符串如何变成具体实例。
- [ ] 理解内建注册、延迟导入与未知 Provider 错误。
- [ ] 对比 LLMFactory、EmbeddingFactory、RerankerFactory、VectorStoreFactory。

### 4.3 空对象与优雅降级

- [ ] 阅读 `NoneReranker`、`NoneEvaluator`、`NoneAnswerGenerator`、`NoneAgent`。
- [ ] 区分“关闭功能”“后端失败”“配置错误”三类情况。

### 4.4 Provider 实现比较

- [ ] 比较 OpenAI/Azure/DeepSeek/Qwen/Ollama 适配方式。
- [ ] 理解 OpenAI-compatible 接口带来的复用与边界。

本章验收：口述新增一个 Provider 所需的最小代码、配置和测试改动。

## 第 5 章：数据摄取流水线

### 5.1 文件完整性与 PDF 加载

- [ ] 阅读 SHA256 与 SQLite 摄取历史。
- [ ] 阅读 PDF → Markdown、图片占位符和图片元数据。

### 5.2 文档切块

- [ ] 阅读 `DocumentChunker` 与 `RecursiveSplitter`。
- [ ] 理解 chunk size、overlap、边界和 source traceability。

### 5.3 Transform 链

- [ ] 阅读 ChunkRefiner 的规则与可选 LLM 增强。
- [ ] 阅读 MetadataEnricher 的规则、Prompt 与降级。
- [ ] 阅读 ImageCaptioner 的图片定位、Vision LLM 与 caption 回填。

### 5.4 Dense 与 Sparse 编码

- [ ] 追踪批量 Dense Embedding。
- [ ] 理解 SparseEncoder 的词频统计与 BM25 的关系。
- [ ] 区分“Chunk 自带 sparse_vector”和“持久化 BM25 索引”。

### 5.5 多存储写入与一致性

- [ ] 阅读 VectorUpserter、BM25Indexer、ImageStorage。
- [ ] 理解稳定 ID、幂等 upsert、部分失败和补偿风险。

### 5.6 Pipeline 编排

- [ ] 分段阅读 `IngestionPipeline.run()`。
- [ ] 画出每阶段输入/输出、Trace、进度回调和异常边界。
- [ ] 用一个样例文档观察真实摄取结果。

本章验收：从一份 PDF 反查出其 Chroma 记录、BM25 条目、图片和版本记录。

## 第 6 章：混合检索流水线

### 6.1 QueryProcessor

- [ ] 理解中英文关键词提取、停用词、filters、query expansion。

### 6.2 Dense Retrieval

- [ ] 追踪 query embedding → Chroma query → RetrievalResult。
- [ ] 理解相似度/距离与分数规范化。

### 6.3 Sparse Retrieval

- [ ] 追踪 jieba 分词、BM25 加载、打分与过滤。
- [ ] 理解专有名词、精确词匹配为何受益于稀疏检索。

### 6.4 RRF Fusion

- [ ] 手算一个小型 Reciprocal Rank Fusion 示例。
- [ ] 理解 RRF 为什么融合排名而不是直接融合异构分数。
- [ ] 阅读去重和 provenance 保留逻辑。

### 6.5 Rerank

- [ ] 比较 None、Cross-Encoder、LLM Reranker。
- [ ] 理解 top-k 截断、超时/异常 fallback 与 Trace 快照。

### 6.6 HybridSearch 编排

- [ ] 分段阅读 `HybridSearch.search()`。
- [ ] 对照 Trace 观察 Dense/Sparse/Fusion/Rerank 前后变化。
- [ ] 解释单路失败时系统为何仍可返回结果。

本章验收：给出一组 Dense 与 Sparse 排名，手算融合结果，并预测开启重排后的影响。

## 第 7 章：回答、引用与多模态响应

### 7.1 Answer Generator

- [ ] 比较 None/Extractive/Template/LLM 四种回答策略。
- [ ] 理解检索结果、上下文预算、Prompt 与生成答案的关系。

### 7.2 引用完整性

- [ ] 阅读 CitationGenerator 与 citation marker 清洗。
- [ ] 理解无效引用、来源去重、置信度和无结果响应。

### 7.3 多模态组装

- [ ] 阅读 MultimodalAssembler 的图片解析、去重、大小限制和编码。
- [ ] 追踪 MCP TextContent/ImageContent 的排列。

本章验收：判断一个生成答案中的 `[n]` 是否能安全映射到真实检索证据。

## 第 8 章：MCP 服务与工具边界

### 8.1 stdio 与 JSON-RPC/MCP 生命周期

- [ ] 理解 initialize → initialized → tools/list → tools/call。
- [ ] 解释为什么 stdout 只能输出协议消息。

### 8.2 ProtocolHandler

- [ ] 阅读工具注册表、schema 暴露、调用分派和异常封装。
- [ ] 理解 Python 参数错误如何变成 MCP error result。

### 8.3 四个 Tool

- [ ] 分别阅读 query、agent_query、list_collections、get_document_summary。
- [ ] 比较工具实例缓存、配置加载、输入 schema 和输出格式。

### 8.4 线协议验证

- [ ] 阅读 E2E MCP Client 测试。
- [ ] 手工发送一次 initialize 和 tools/list。
- [ ] 确认当前实际工具数，并记录与旧文档的差异。

本章验收：能新增一个只读 MCP Tool，并写出 protocol-level 测试。

## 第 9 章：Agentic RAG

### 9.1 直接 RAG 与 Agentic RAG

- [ ] 对比固定检索链和动态工具循环的控制权差异。
- [ ] 明确 Agent 带来的能力、成本、延迟与失败面。

### 9.2 AgentFactory 与三种策略

- [ ] 阅读 ReAct、Plan-and-Execute、Self-Ask 的公共循环和差异点。
- [ ] 理解最大迭代数与最终降级。

### 9.3 路由、查询理解与工具白名单

- [ ] 阅读 Rule/LLM/Null Router。
- [ ] 阅读 QueryUnderstanding 与 ToolRegistry。
- [ ] 理解白名单和参数构造的安全边界。

### 9.4 记忆与反思

- [ ] 阅读 None/SQLite Memory。
- [ ] 阅读 RetrievalReflector 的判定、改写与轮次限制。
- [ ] 区分“会话记忆”和“知识库检索证据”。

### 9.5 Agent 查询全链路

- [ ] 从 MCP `agent_query` 追踪到 AgentResult 和 MCPToolResponse。
- [ ] 用测试覆盖 LLM 失败、非法工具、空结果和迭代耗尽。

本章验收：能画出一次 ReAct 循环，并说明每个停止或降级条件。

## 第 10 章：文档生命周期与数据版本

### 10.1 DocumentManager

- [ ] 理解跨 Chroma、BM25、SQLite、图片目录的聚合视图。

### 10.2 删除事务与回滚

- [ ] 阅读 transactional delete、失败恢复和一致性测试。

### 10.3 版本快照与回滚

- [ ] 阅读 DocumentVersionStore、内容快照、版本查询和 rollback。

### 10.4 孤儿数据回收

- [ ] 阅读 OrphanGC 的 dry-run、判定依据和删除边界。

本章验收：解释一次文档更新或删除会触及哪些存储，以及失败后如何恢复一致性。

## 第 11 章：可观测性与 Dashboard

### 11.1 Trace 基础设施

- [ ] 阅读 TraceContext、TraceCollector、JSONL logger。
- [ ] 理解 trace_id、stage、timing、snapshot 和 finish。

### 11.2 摄取 Trace

- [ ] 将 Pipeline 各阶段映射到摄取追踪页面。

### 11.3 查询 Trace

- [ ] 将 QueryProcessor、双路召回、融合、重排、生成映射到查询追踪页面。

### 11.4 Dashboard 架构

- [ ] 阅读 Streamlit 六页面和三类 service。
- [ ] 区分 UI 逻辑、数据服务和业务核心。

本章验收：给定一条慢/差查询，能从 Trace 判断问题发生在哪一阶段。

## 第 12 章：评估、测试与质量闭环

### 12.1 Golden Test Set

- [ ] 阅读测试集 schema、加载校验与单条 QueryResult。

### 12.2 自定义与 Ragas 指标

- [ ] 区分检索指标与生成指标。
- [ ] 理解 Custom、Ragas、Composite Evaluator 的适用条件与依赖。

### 12.3 EvalRunner 与报告

- [ ] 追踪批量执行、聚合、失败隔离、HTML 报告和历史记录。

### 12.4 Ablation

- [ ] 理解关闭 sparse/rerank 等变体如何验证组件贡献。

### 12.5 测试金字塔与 CI

- [ ] 盘点 unit/integration/e2e/llm/slow markers。
- [ ] 为关键契约分别找到单测、集成测试和 E2E 证据。
- [ ] 复查当前 pytest 临时目录权限现象，区分环境错误与断言失败。

本章验收：为一次检索优化设计离线指标、消融实验和回归门槛。

## 第 13 章：工程演进、文档漂移与设计取舍

### 13.1 从 Spec 到实现

- [ ] 选取一个功能，对照 DEV_SPEC、代码、测试和开发日志。
- [ ] 识别“设计意图”“最终实现”“后续演进”的差异。

### 13.2 当前文档漂移

- [ ] 核对 MCP Tool 数量：旧文档 3 个，当前代码 4 个。
- [ ] 核对 ARCHITECTURE 基于旧 commit 的结构与当前 Agent/版本管理模块。
- [ ] 整理其他过期的路径、数量、配置或运行说明。

### 13.3 设计评价

- [ ] 总结做得好的抽象、关键技术债、复杂度热点和潜在生产风险。
- [ ] 区分教学项目中的合理简化与生产系统必须补齐的能力。

本章验收：能基于代码证据做一份有取舍、有优先级的架构评价。

## 第 14 章：综合实战与学习笔记收口

### 14.1 选定小型扩展

- [ ] 从新 Provider、新 Tool、新指标、新加载器或新检索策略中选择一项。
- [ ] 写清需求、影响面、验收标准和不做事项。

### 14.2 实现与验证

- [ ] 完成代码与配置接入。
- [ ] 补齐单元/集成测试与 Trace 证据。
- [ ] 运行相关回归并记录结果。

### 14.3 反向讲解

- [ ] 从用户请求出发讲完整在线链路。
- [ ] 从一份新文档出发讲完整离线链路。
- [ ] 回答常见设计追问与故障场景。

### 14.4 正式学习笔记

- [ ] 汇总每节的“一句话结论、调用链、设计取舍、易错点、验证证据”。
- [ ] 统一术语，去掉伴读过程中的重复和临时信息。
- [ ] 加入最终架构图、两条时序/流程图、核心类型表和扩展指南。
- [ ] 完成两轮人工通读与修订。

## 每节笔记素材模板

```markdown
### 小节标题

- 一句话结论：
- 它解决的问题：
- 所在层与上下游：
- 关键入口：
- 核心调用链：
- 重要数据结构：
- 设计取舍：
- 降级/异常路径：
- 动手验证与结果：
- 我还不能解释的问题：
- 用自己的话复述：
- 高频面试题：
- 我的回答：
- 追问与改进版回答：
```

## 面试题使用约定

- 基础题：检查概念是否准确，例如“为什么需要文档切块？”
- 代码题：要求结合本项目入口或调用链，例如“`force=True` 绕过了哪一步，哪些步骤仍然执行？”
- 场景题：给出规模、故障或变更条件，例如“百万文档摄取时当前串行 Pipeline 会遇到什么问题？”
- 取舍题：解释选型边界，例如“为什么同时保留 Dense 与 BM25，而不是只使用向量检索？”
- 诊断题：根据现象定位阶段，例如“Chroma 有数据而 BM25 没数据，会造成什么查询表现？”
- 每个普通小节默认 2～4 题，避免题量压过代码理解；章节收口时再进行一轮连续追问式模拟面试。

## 伴读记录

### 2026-08-12｜初始化与第 1.1 节开始

- 已完成仓库规模、模块、依赖、入口和文档体系盘点。
- 已建立 Deep Research 伴读路线，以代码/测试为事实源。
- 环境自检 9/9 PASS；核心类型、ProtocolHandler、RRF 代表测试 78 passed。
- 发现旧架构文档未覆盖最新 Agentic RAG 与第 4 个 MCP Tool。
- 当前停点：第 1.1 节“最小心智模型”。
- 下次起点：用“离线摄取链 + 在线查询链 + 两个外部入口”讲清项目全景。

### 2026-08-12｜第 1.1 节第一次复述

- 已能区分离线摄取（准备可检索数据）与在线查询（消费检索数据）。
- 已初步区分 `src/libs` 的可替换基础能力与 `src/core` 的领域契约/核心策略；需继续留意编排并不全在 `core`，摄取编排位于 `src/ingestion`。
- 已理解 Agentic RAG 在固定 RAG 链路上增加是否检索、证据是否充分、是否再次检索等动态决策。
- 当前停点：补齐四类外部边界，并亲手画出不超过 12 个节点的全景图。

### 2026-08-12｜暂结第 1.1 节，推进到第 1.2 节

- 全景图练习按学习者选择暂时跳过，保留为 `[!]` 待补项，不记作已完成。
- 第 1.1 节核心概念已经建立，不让绘图练习阻塞主线学习。
- 当前停点：第 1.2 节“离线摄取主链”，从 `scripts/ingest.py` 追踪到 `IngestionPipeline`。

### 2026-08-12｜第 1.2.1 节开始：CLI 到 Pipeline

- 已定位 CLI 调用链：`main()` → `parse_args()` → `load_settings()` → `discover_files()` → `IngestionPipeline(...)` → 对每个文件调用 `pipeline.run()`。
- 已确认职责边界：CLI 管理批次和退出码，Pipeline 初始化负责组件装配，`run()` 只加工一个文件。
- 已执行目录 dry-run：成功加载配置，递归发现 7 个 PDF，未初始化或运行 Pipeline，exit code 0。
- 当前停点：完成 1.2.1 的复述验证，再进入 Pipeline 六阶段。

### 2026-08-12｜第 1.2.1 节第一次复述

- 已正确理解 Pipeline 对整个批次只初始化一次，以及部分失败时命令返回 exit code 1。
- 待校准：7 个被发现的文件都会调用 `pipeline.run()`；“内容未变化而跳过”是在 `run()` 内完成 SHA256 检查后才得出的结果，因此调用次数是 7，不是 6。
- 当前停点：确认“调用 `run()` 不等于执行完六个阶段”这一边界后，完成 1.2.1。

### 2026-08-12｜完成第 1.2.1，进入第 1.2.2

- 已掌握“一次有效 CLI 批次初始化一个 Pipeline；每个已发现文件调用一次 `run()`；是否跳过由 `run()` 的第一阶段决定”。
- 第 1.2.1 标记完成。
- 已核对当前 `run()` 的六阶段：integrity → load → split → transform → embed → upsert。
- 已确认错误边界：阶段 4 的 LLM 增强可局部规则降级；主阶段未处理异常则由外层捕获并返回失败结果。
- 当前停点：第 1.2.2 六阶段的输入、输出与阶段间类型变化。

### 2026-08-12｜完成第 1.2.2

- 已能按顺序解释 integrity → load → split → transform → embed → upsert。
- 已掌握核心类型变化：`Path → Document → List[Chunk] → 增强后的 List[Chunk] → Dense vectors + Sparse stats → 持久化数据`。
- 复述验证 4/4：正确判断规则降级后 Pipeline 成功、10 个 Chunk 对应 10 个 Dense 向量、失败增强的 Chunk 不丢弃，以及 split 首次完成一对多转换。
- 当前停点：第 1.2.3“多存储落点”，理解同一 Chunk 为什么要分布到多种存储及如何通过 ID 关联。

### 2026-08-12｜伴读方式调整：加入面试训练

- 后续每节问题升级为基础理解、代码追问、面试场景三层，重点内容增加设计取舍和故障诊断。
- 每次回答后除判断正误外，还会从面试表达角度校准完整性，并沉淀可复用的回答框架。
- 每章结束安排一次连续追问式模拟面试，同时继续以真实代码和测试证据为准。

### 2026-08-13｜第 1.2.3 节开始：多存储落点

- 已核对检索数据分工：Chroma 保存稳定 `chunk_id`、Dense 向量、正文和 metadata；BM25 JSON 保存词项、IDF、posting 及同一个 `chunk_id`。
- 已核对稀疏读取链：BM25 返回 `chunk_id + score`，`SparseRetriever` 再通过 Chroma `get_by_ids()` 补齐正文和 metadata。
- 已核对治理与资产存储：`ingestion_history.db` 保存摄取状态和文档版本账本，`image_index.db` 保存图片索引，图片文件和版本快照位于文件系统。
- 已识别面试重点：专用存储的职责分工、稳定 ID 关联、跨存储部分写入风险，以及幂等重试/清理策略。
- 当前停点：完成 1.2.3 的基础、代码和场景题验证。

### 2026-08-13｜第 1.2.3 节第一次面试训练

- 基础题方向正确：已认识到 BM25 与 Chroma 保存的数据职责不同；需补全为“BM25 返回 `chunk_id + score`，再到 Chroma 获取正文和 metadata”。
- 稳定 ID 题待巩固：路径 hash 用于区分/归组来源文档，`chunk_index` 表示文档内位置但不能单独保证唯一，内容 hash 用于感知内容变化和保证相同内容幂等。
- 故障题回答正确：Chroma 成功、BM25 失败时 Pipeline 整体失败；Dense 可能可用而 Sparse 缺失/陈旧；失败状态使下一次摄取可以重试。
- 设计取舍题已建立“收益/代价”框架，待补保障措施（稳定 ID、幂等 upsert、失败重试、原子文件替换、版本清理/孤儿 GC）与生产改进（事务元数据中心、outbox/事件日志、对账修复、监控告警）。
- 当前停点：用自己的话完成一版多存储设计回答后结束 1.2.3。

### 2026-08-13｜完成第 1.2.3

- 已能说明多存储的职责分工：Chroma 负责 Dense 检索与完整 Chunk，BM25 负责关键词倒排检索，SQLite 负责摄取/版本治理，文件系统负责图片与快照。
- 已能从收益、代价和保障措施解释多存储设计，并提到幂等 upsert、失败重试、BM25 原子替换、对账修复与一致性监控。
- 面试表达待持续校准：BM25 不是简单按“词频次序”检索，而是综合 TF、IDF 和文档长度归一化计算相关性；当前项目已有的保障与建议的生产增强应分开表述。
- 第 1.2.3 标记完成；当前停点推进到第 1.2.4“幂等与更新”。

### 2026-08-13｜第 1.2.4 节开始：幂等与更新

- 已核对三种执行语义：普通重复摄取按成功 `file_hash` 跳过；`force=True` 仍计算 hash 但绕过跳过并重跑；同路径内容变化产生新 hash 并进入更新流程。
- 已核对多层幂等：文件级 SHA256 避免无效重算，稳定 `chunk_id` 使 Chroma upsert 可重复，BM25 按路径前缀移除旧 posting 后重建，快照按 `{collection}/{file_hash}` 复用。
- 已核对版本切换：新数据成功写入后，版本账本才将旧版本置为非活动并激活新版本；失败版本记录为非活动，不取代旧活动版本。
- 已核对旧数据清理：BM25 在重建时按路径前缀清旧数据；Chroma 按 `source_path + old_hash` 精确删除；旧 hash 不再被任何活动版本引用时才删除图片与历史记录。
- 当前实现限制待记忆：`should_skip()` 只按全局 `file_hash` 判断，没有纳入路径和 collection；相同字节内容首次写入另一位置/collection 时，普通模式可能被跳过，需要 `force=True`。这是基于当前代码的实现边界。
- 当前停点：完成幂等、强制重跑、更新失败和清理策略的面试题验证。

## 待调查清单

- [ ] pytest 在当前 Windows 环境中创建/清理部分临时目录时出现 `PermissionError` 的具体环境原因。
- [ ] README、ARCHITECTURE、REPRODUCE 与当前 Agentic RAG 代码之间的完整漂移清单。
- [ ] `pyproject.toml` 要求 Python 3.12，但 ruff/mypy target 仍为 3.10 的意图或遗留原因。
- [ ] 当前运行数据中的 collection 默认值是否在所有 CLI、配置和 Dashboard 中一致。
