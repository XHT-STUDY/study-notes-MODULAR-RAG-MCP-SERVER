# Agent 算法 / LLM 应用开发岗位与面试资料核查

核查日期：2026-09-24（北京时间）。用途：为本仓库项目经历、简历改写和面试准备提供外部市场依据。以下是**定向样本**，不能推断全部招聘市场的占比或薪资水平。岗位页面可能随时关闭；投递前重新打开原链接确认。

## 样本与证据等级

| 来源 | 地区、资历及核查状态 | 原文支持的关键信号 |
| --- | --- | --- |
| [百度 2027 校招：Agent 应用全栈工程师](https://talent.baidu.com/jobs/detail/GRADUATE/6f9c3a86-6557-409d-8fa7-e6f4c68d6765) | 北京，2026-07-21 发布；2026-09-24 页面仍展示“申请职位”说明 | 规划—执行—反思闭环、工具/API、记忆、状态、多 Agent、RAG 和 Agent 评测；明确接受课程或自发 Agent 项目。 |
| [百度 2027 校招：智能体算法工程师](https://talent.baidu.com/jobs/detail/GRADUATE/4f1cbc80-8332-4a92-b8fa-c0132b17d47e) | 北京，2026-08-03 发布；核查时页面仍展示“申请职位”说明；要求硕士及以上 | Agent 规划、工具调用、反思与代码生成能力优化，RAG 融合、评测；要求 Prompt / 微调实践，强化学习或规划算法、论文/开源贡献为优先项。 |
| [百度日常实习：大模型应用 / Agent 算法工程师](https://talent.baidu.com/jobs/detail/INTERN/1a0bfe96-f59c-4384-9525-79fdf324c67f) | 北京，2026-07-21 发布；核查时页面仍展示“申请职位”说明；要求硕士及以上 | router、plan、RAG、生成、工具/Deep Research 的效果优化，评估—优化—验证闭环；还要求 Transformer、PyTorch、后训练与 RL 知识。 |
| [百度社招：Agent 引擎开发工程师](https://talent.baidu.com/jobs/detail/SOCIAL/d56ce9b0-296b-4615-9497-115968d4fc14) | 北京，2026-07-29 发布；核查时详情页可访问；要求 3 年以上后端经验 | 运行引擎、插件、记忆、模型路由；状态持久化、限流重试、trace、安全隔离与高风险操作确认。 |
| [Binance：AI Agent Engineer](https://jobs.lever.co/binance/3a2ca7e0-e2c9-4248-b8fe-0de5d05dee1c) | 台北 / 亚洲，要求 1 年以上 LLM、RAG、Agent 生产实践；核查时有申请入口，页面未见发布日期 | 设计可自适应、多跳的 Agentic RAG；构造基准和标注策略，测量检索效率、延迟、回答有据性和任务成功率；根据真实反馈迭代。 |
| [Mitratech：Senior Software Engineer - AI/ML](https://job-boards.greenhouse.io/mitratech/jobs/8038251) | 德国远程，高级岗；核查时有 Apply，页面未见发布日期 | 端到端 RAG（摄取、切块、embedding、召回、重排、答案）、Agent 编排与状态/回退；生成质量评测、可观测、回滚和生产级 Python。 |
| [Prodigal：Agent Engineer](https://job-boards.greenhouse.io/prodigal/jobs/4651355007) | 招聘页写 1–3 年经验；核查时有申请表，页面未见发布日期 | 从需求界定到上线监控及迭代的完整负责；围绕准确率、延迟、可靠性优化；与客户一起确认工作流和业务结果。 |
| [Osano：Senior AI Engineer](https://job-boards.greenhouse.io/osano/jobs/5390304008) | 美国远程，要求 5 年以上；核查时有申请表，页面未见发布日期 | 要求严格遵循来源的 RAG、引用完整性、输出校验；用准确率、引用遵循率、延迟、可靠性驱动迭代。 |
| [CodeRoad：Agentic AI Engineer](https://job-boards.greenhouse.io/coderoad/jobs/4406476009) | 拉美，要求 3 年以上；核查时有 Apply，页面未见发布日期 | 工具/API/MCP 接入、检索优化、自动化评测、回归测试、注入与泄漏防护、部署和故障诊断。 |

这些是招聘方直接发布的 JD。样本包含中国内地校招、实习、社招，以及国际工程岗位，但仍是**定向样本，不代表全市场平均门槛**。它们适合辨识能力方向，不适合把其中的生产要求直接写成个人项目的已达成成果。搜索结果中另有旧职位页面被招聘系统重定向到公司职位列表，因此未当作当前在招证据。

## JD 共性与两类岗位差异

1. **可解释的端到端技术决策。** 多个招聘方要求把业务目标转成检索、生成、工具调用、校验的完整方案，并解释切块、索引、召回、重排、模型选型、成本、时延的取舍。单写“使用 LangChain / 向量库 / MCP”缺少责任范围和效果。证据：[Mitratech](https://job-boards.greenhouse.io/mitratech/jobs/8038251)、[Binance](https://jobs.lever.co/binance/3a2ca7e0-e2c9-4248-b8fe-0de5d05dee1c)、[Prodigal](https://job-boards.greenhouse.io/prodigal/jobs/4651355007)。
2. **评测是交付的一部分。** 既看检索/有据性，也看任务成功、引用质量、异常恢复、时延和回归；数据集、标注和失败案例需要说得清。证据：[Binance](https://jobs.lever.co/binance/3a2ca7e0-e2c9-4248-b8fe-0de5d05dee1c)、[Mitratech](https://job-boards.greenhouse.io/mitratech/jobs/8038251)、[Osano](https://job-boards.greenhouse.io/osano/jobs/5390304008)。
3. **可靠性与安全会被具体追问。** 工具失败后的回退、状态管理、结构化输出校验、敏感数据保护、注入防护和可观测性在多个 JD 中是明确职责。证据：[Mitratech](https://job-boards.greenhouse.io/mitratech/jobs/8038251)、[Osano](https://job-boards.greenhouse.io/osano/jobs/5390304008)、[CodeRoad](https://job-boards.greenhouse.io/coderoad/jobs/4406476009)。
4. **“Agent 算法”方向的加分点不同于一般应用集成。** Binance 明确写出自适应检索、多跳查询拆解、研究性实验、benchmark 与任务成功率；应用工程岗位更直接强调上线、监控、用户工作流、API 接入和故障处理。这是对上述**样本的归纳**，并非所有同名职位的统一定义。证据：[Binance](https://jobs.lever.co/binance/3a2ca7e0-e2c9-4248-b8fe-0de5d05dee1c)、[Prodigal](https://job-boards.greenhouse.io/prodigal/jobs/4651355007)、[CodeRoad](https://job-boards.greenhouse.io/coderoad/jobs/4406476009)。

### 中文岗位定位：应用工程、Agent 算法、模型训练

百度的两条 **2027 校招**职位很好地划出了准备重点：[Agent 应用全栈](https://talent.baidu.com/jobs/detail/GRADUATE/6f9c3a86-6557-409d-8fa7-e6f4c68d6765)接受课程或自发项目，更看完整任务闭环、工具/记忆/状态/RAG 集成、评测和用户体验；[智能体算法](https://talent.baidu.com/jobs/detail/GRADUATE/4f1cbc80-8332-4a92-b8fa-c0132b17d47e)要求硕士及以上，进一步看规划、工具调用等能力的算法优化、Prompt/微调实践，并把 RL、规划算法和论文/开源列为优先项。百度的[算法实习岗](https://talent.baidu.com/jobs/detail/INTERN/1a0bfe96-f59c-4384-9525-79fdf324c67f)还直接要求 Transformer、PyTorch 和后训练算法；因此“Agent 算法”这个标题有时确实覆盖模型训练，**仅有应用集成项目未必满足其硬性条件**。这属于对这三份 JD 的逐条比较。

同属 Agent 方向的[百度引擎开发社招岗](https://talent.baidu.com/jobs/detail/SOCIAL/d56ce9b0-296b-4615-9497-115968d4fc14)则偏底层平台和后端：运行时、异步消息、持久化、限流、日志、隔离与安全。个人 RAG/MCP 项目更适合优先对准“LLM 应用开发 / Agent 应用工程”岗位；冲击算法岗时，要用自己确实完成的评测、策略改进与实验设计支撑表述，不可暗示未做过的 SFT/RL、规模化上线或论文成果。[百度应用全栈](https://talent.baidu.com/jobs/detail/GRADUATE/6f9c3a86-6557-409d-8fa7-e6f4c68d6765)、[百度算法](https://talent.baidu.com/jobs/detail/GRADUATE/4f1cbc80-8332-4a92-b8fa-c0132b17d47e)。

## 一手面经与招聘方指引

以下牛客内容为发帖人**自述**，无法独立核验是否真的发生、是否完整、是否能代表对应公司。可用于准备追问，不能当作某公司固定题库或录用标准。

| 来源 | 发帖时间 / 自述场景 | 对本项目的启发 |
| --- | --- | --- |
| [腾讯 AI 应用开发后端实习面经](https://www.nowcoder.com/feed/main/detail/144c6ae334b24c0aa643ed43ccfebaac) | 页面显示 04-23；发帖人称约 40 分钟项目深挖 | 问有没有真实用户、为什么未上线、Agent 失败或中断时的重试安全、RAG 知识库不停服更新，并有金融场景安全设计和算法题。准备时应坦陈个人项目状态，拿出失败处理与验证证据。 |
| [字节 Agent 开发实习一面面经](https://www.nowcoder.com/feed/main/detail/6506d4b4addf447c8e2c135b5088cdc8) | 页面显示 03-19；发帖人自述实习一面 | 问上下文压缩、RAG 流程、MCP 与 Skill 原理、项目细节和代码题。准备时应能从请求到工具响应逐步画出链路。 |
| [联影 Agent 开发一面面经](https://www.nowcoder.com/feed/main/detail/d5a9001f0d5048518ad85c494d1f6d54) | 页面显示 07-08；发帖人自述一面 | 问模型/embedding 选型、双路召回数量、重排是否必要、分块规模、离线部署约束；同时问 Python 并发和模型采样参数。要能解释选择依据与边界。 |

招聘方公开指引更可靠：[Microsoft 技术面试说明](https://careers.microsoft.com/v2/global/en/hiring-tips/technical-interviewing)写明会看问题拆解、设计、可运行代码、测试、算法/数据结构，AI/ML 职位还看模型评估和优化；[Microsoft 面试建议](https://careers.microsoft.com/v2/global/en/hiring-tips/interview-tips.html)要求用具体经历说明情境、行动、结果与反思；[OpenAI 面试指南](https://openai.com/interview-guide/)强调快速学习并产出结果，技术评估可能是结对编程、作业或技术测试，面试重视如何思考和解释决策。它们说明**能复盘自己做的决策并验证结果**比背框架名更有说服力，也提醒不要放松编码与基础知识。

## 用于个人项目简历的实操结论

- 首句交代**问题、目标使用者、约束和自己负责的范围**；随后写关键决策、验证方式和可复现成果。若没有正式用户和线上指标，明确写“个人项目 / 原型 / 离线评测”，不能把实验表现写成业务收益。依据是上述 JD 对端到端责任和结果的要求，以及面经中对上线状态与本人贡献的追问。[Prodigal](https://job-boards.greenhouse.io/prodigal/jobs/4651355007)、[腾讯面经](https://www.nowcoder.com/feed/main/detail/144c6ae334b24c0aa643ed43ccfebaac)。
- 每个“提升”都应有**基线、样本、指标、前后结果和复现方法**；没有对比实验时，改写为“实现了 X 能力 / 覆盖了 Y 场景”，避免虚构百分比、吞吐量和生产成本节省。[Binance](https://jobs.lever.co/binance/3a2ca7e0-e2c9-4248-b8fe-0de5d05dee1c)、[Osano](https://job-boards.greenhouse.io/osano/jobs/5390304008)。
- Agent 算法版优先讲检索/规划策略、评测集、消融与错误分析；LLM 应用版优先讲业务流程、接口与工具集成、异常路径、可观测和交付。两版都需准备 RAG 全链路、效果评估、为何选这套架构、失败如何定位、替代方案的代价。[Binance](https://jobs.lever.co/binance/3a2ca7e0-e2c9-4248-b8fe-0de5d05dee1c)、[Mitratech](https://job-boards.greenhouse.io/mitratech/jobs/8038251)、[联影面经](https://www.nowcoder.com/feed/main/detail/d5a9001f0d5048518ad85c494d1f6d54)。
- 面试准备可按顺序组织证据：一句话背景 → 自己的模块 → 一次真实故障或失败样例 → 方案对比 → 测量方法与结果 → 下一步；另准备可运行代码题和 Python/数据库/并发基础。招聘方指引和一手面经均支持这种准备方向，但**具体题目不可预测**。[Microsoft 技术面试说明](https://careers.microsoft.com/v2/global/en/hiring-tips/technical-interviewing)、[OpenAI 面试指南](https://openai.com/interview-guide/)、[腾讯面经](https://www.nowcoder.com/feed/main/detail/144c6ae334b24c0aa643ed43ccfebaac)。

## 尚不能从外部资料得出的结论

没有可信依据可推断本项目已经带来企业降本、真实用户增长、线上可用性或优于行业基准。以上 JD 也不能证明某岗位在用户所在地开放投递，或证明上述面经题目的真实性与出现概率。此类主张必须另用仓库代码、测试记录、个人实际经历或招聘方最新页面核验。
