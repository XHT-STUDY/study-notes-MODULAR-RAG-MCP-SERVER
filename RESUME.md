# 简历项目经历｜企业流程制度智能问答系统

> 面向岗位：LLM 应用开发工程师、Agent 应用/算法工程师。投递前将项目时间替换为真实起止时间。

## 中文版

**企业流程制度智能问答系统（RAG + Agent）｜个人项目｜独立设计与开发｜[真实起止时间]**

**背景**：面向公司内部流程与制度问答场景，员工查询报销、请假、入职或审批规则时，需要从较长的制度文档中定位具体条款并核对答案来源；关键词不一致、制度版本更新和缺少引用会增加查找与核对成本。围绕这一问题，设计从文档摄取到检索、回答和 Agent 调用的知识问答系统。

**个人工作与产出**：

- **构建文档摄取与更新链路**：完成 PDF 解析、切块、内容增强及双索引写入；文件哈希跳过重复摄取，版本回滚与协调删除降低旧索引残留风险。
- **设计可降级的混合检索**：实现 Dense/BM25 双路召回、RRF 融合与可选重排；单路或重排失败时回退可用结果，并通过阶段追踪定位故障。
- **把知识库接入 Agent 工具链**：通过 MCP 暴露检索、集合、摘要及 Agent 查询 **4 个工具**；实现 **3 种 Agent 策略**，以白名单和迭代上限约束调用。
- **建立可复查的检索评测**：修复指标恒零问题，补齐来源级指标和 **4 组消融**；5 条样例查询中 Sparse MRR **0.8667** 高于 Hybrid **0.7667**。
- **提高问题定位与复用能力**：抽象模型、Embedding 和重排接口，支持配置切换；结合摄取、查询、Agent 追踪与管理界面定位失败阶段。
- **验证关键路径**：运行 Agent、融合、重排回退和评测专项回归，本次本机 **113/113 个测试通过**，形成可重复执行的质量检查。

**技术关键词**：Python、RAG、Dense Retrieval、BM25、RRF、Rerank、MCP、Agent Tool Calling、Chroma、评测与链路追踪。

## English version

**Internal Policy and Workflow Q&A System (RAG + Agent) | Personal project | Independent developer | [Actual dates]**

**Context**: Designed for questions about internal policies and workflows, such as leave, reimbursement, onboarding, and approvals. Finding the right clause in long documents and checking its source can be difficult when wording differs or policies change. I built a document-to-answer workflow that combines retrieval, cited responses, and agent access.

**Contributions and outcomes**:

- **Built the document ingestion and update pipeline** for PDF parsing, chunking, metadata and image-caption enrichment, and dense/BM25 indexing. File hashes skip unchanged inputs; version snapshots, rollback, and coordinated deletion reduce duplicate work and stale-index risk.
- **Designed a resilient retrieval path** with dense and BM25 recall, RRF fusion, and optional reranking. If one retrieval path or the reranker fails, the system falls back to available results; stage traces identify where a query failed.
- **Exposed the knowledge base to agents** through four MCP tools for retrieval, collection listing, document summaries, and agent queries. Three configurable agent strategies use a tool allowlist, an iteration limit, and citation validation to constrain invalid calls and runaway loops.
- **Made retrieval quality measurable** by fixing missing evaluation labels, adding source-level metrics, and comparing four retrieval variants. On a five-query exploratory set, sparse retrieval achieved Source MRR 0.8667 versus 0.7667 for hybrid retrieval, identifying a concrete need for broader evaluation and tuning.
- **Improved diagnosability and reuse** with configuration-driven model, embedding, and reranker components, plus ingestion, query, and agent traces and a management dashboard for inspecting data and evaluation results.
- **Validated critical paths** with a focused regression run covering agent loops, rank fusion, reranker fallback, and metric calculation: **113 of 113 tests passed** in the current local run.

**Keywords**: Python, RAG, Dense Retrieval, BM25, RRF, Reranking, MCP, Agent Tool Calling, Chroma, evaluation, tracing.

## 投递前核对

- 本文按已确认的个人项目事实写作。岗位场景是公司流程制度问答；目前的探索性评测使用样例 PDF，不代表真实企业部署效果。
- 5 条样例查询仅用于验证评测链路和发现策略差异，不能当作通用准确率。写入简历的数字是 **4 个 MCP 工具、3 种 Agent 策略、4 组消融配置、113/113 个专项测试**，以及带样本规模说明的 Source MRR 对比。
- 旧稿中的“200 条黄金集、2000+ 篇公司文档、92% 命中率、800ms 延迟、员工自助覆盖率和 HR 答疑量下降”没有对应实测证据，本版已移除。
- 投递 Agent 算法岗时，可将“Agent 工具链”和“检索评测”移到前两条；投递 LLM 应用岗时，保持当前顺序。不要把三种 Agent 策略表述成多 Agent 协作或模型训练成果。

项目实现和验证依据见 [README](README.md)、[Agent 实现](src/core/agent/agent_runner.py)、[检索实现](src/core/query_engine/hybrid_search.py)、[评测记录](DEVELOPMENT_LOG.md)及[求职攻略](docs/agent-llm-resume-guide.md)。
