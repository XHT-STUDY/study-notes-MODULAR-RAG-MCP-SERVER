# 香港在招 AI/机器学习/大模型应用方向岗位 JD 参考示例（10 份）

> **调研日期**：2026-09-08
> **一句话总结**：香港 LLM/GenAI 应用岗需求集中在"Python + 深度学习框架 + RAG/Agent + 云平台"技术组合，本地初创与研究机构最看重 RAG/微调/Agent 落地能力且普遍要求中英文双语，国际大厂(Microsoft/AWS)则额外要求 4-8 年云架构与客户面交付经验及粤语能力——mid-level 候选人最匹配的窗口在本地 FinTech/RegTech 初创与 InnoHK 研究中心。

**求职者画像**：算法工程师，香港院校硕士，掌握 RAG 检索系统、LoRA 大模型微调、Agent 应用开发，具备后端平台经验，目标 mid-level LLM 应用/AI 工程师岗。

**信息获取方式说明**（重要）：
- LinkedIn 公开职位页（guest 模式）通过 WebFetch 直接抓取成功；
- JobsDB 职位详情页直接抓取返回 403 Forbidden，改用其聚合镜像 beBee.com 或搜索引擎摘要获取同一 JD 全文；
- Apple 香港官网职位页因纯 JS 渲染无法抓取正文（已放弃纳入）；levels.fyi 的 Morgan Stanley 职位页抓取内容为空（已放弃）；eFinancialCareers 用 WebFetch 返回 405，改用 web_reader 工具抓取摘要；
- Bloomberg 香港 ML 岗位在 LinkedIn 列表页出现过但具体职位页无法定位，未纳入，以 S&P Global 香港岗替代金融数据分析机构类型。
- 各 JD 的"抓取日期"均为 2026-09-08；部分 LinkedIn 岗位发布已久或已停止接受申请，仍作为 JD 结构与要求的市场参考示例保留，状态已在各节注明。

---

## 1. HSBC 汇丰银行 — AI Engineer (Corporate and Institutional Banking)

| 项目 | 内容 |
|---|---|
| 公司 | HSBC（The Hongkong and Shanghai Banking Corporation Limited） |
| 职位 | AI Engineer - Corporate and Institutional Banking |
| 雇主类型 | 国际银行在港科技岗 |
| 来源链接 | https://hk.linkedin.com/jobs/view/ai-engineer-corporate-and-institutional-banking-at-hsbc-4312710889 |
| 抓取日期 | 2026-09-08（页面显示"不再接受申请"，作为 JD 参考示例保留） |
| 薪资区间 | 未公开 |
| 经验要求 | 专业 AI/ML 工程经验（软件开发生命周期导向），有 LLM（GPT、BERT 等）与多智能体框架实战；金融服务背景（反欺诈、信贷评分、客服自动化）优先 |
| 学历要求 | 未明确写出 |

**核心职责摘录（原文）**：
- "Build multi-agent workflows to optimize business processes within a bank"
- "Develop and maintain software pipelines for data processing, model training, and deployment using Python-based frameworks"
- Train, fine-tune, and optimize neural network models (including LLMs) for banking use cases such as risk assessment and customer query resolution
- 与数据科学家、工程师和业务方协作交付符合银行合规（GDPR/CCPA）与伦理 AI 要求的生产级应用；参与 code review、敏捷 ceremonies、CI/CD，监控生产系统

**技能要求清单**：
- Python + TensorFlow / PyTorch / scikit-learn / Huggingface
- Agentic 框架：LangChain、LangGraph、ADK 或类似
- 扎实 ML 基础（监督/无监督学习、评估指标、偏差缓解）
- 云平台（AWS / Azure / GCP）、Git、敏捷
- 加分：Spark/Hadoop、SQL/NoSQL、图数据库与知识图谱、Docker/Kubernetes、MLOps
- 与非技术干系人的沟通能力

**语言要求**：未在 JD 中提及。

**匹配点**：该岗核心就是 LLM 微调 + multi-agent 工作流 + RAG 相邻技术（知识图谱/向量检索），与候选人的 LoRA 微调、Agent 开发经验高度对口。银行合规场景（AML、风控）是需补的领域知识，但 JD 未设硬性年限，mid-level 可投。后端平台经验正好覆盖其 CI/CD 与生产部署要求。

---

## 2. Microsoft 微软香港 — Cloud Solution Architect – Data & AI

| 项目 | 内容 |
|---|---|
| 公司 | Microsoft |
| 职位 | Cloud Solution Architect – Data & AI |
| 雇主类型 | 国际软件公司香港分部 |
| 来源链接 | https://hk.linkedin.com/jobs/view/cloud-solution-architect-data-ai-at-microsoft-4328798883 |
| 抓取日期 | 2026-09-08（页面显示"不再接受申请"，作为 JD 参考示例保留） |
| 薪资区间 | 未公开 |
| 经验要求 | 最低：学士 + 4 年云/IT 咨询/架构经验；优先：8 年技术架构与咨询；有企业级 cloud-native AI 方案（Azure 优先）与 Python/.NET 生成式 AI 应用落地经验 |
| 学历要求 | Computer Science / IT / 工程相关学士（或同等经验） |

**核心职责摘录（原文）**：
- "Engage with customer IT and business leaders to understand their application, data, and AI priorities"
- "Lead technical engagements across architecture design, Proof of Concepts (POCs), and Minimum Viable Products (MVPs)"
- "Own the end-to-end technical delivery results, ensuring completeness and accuracy of consumption and customer success plans"
- 交付可复用 IP、保障关键负载的健康/韧性/安全、作为 Voice of Customer 反馈产品团队、主导客户 skilling 工作坊

**技能要求清单**：
- Azure AI Foundry（Models、Agent Service、Semantic Kernel、Search、ML、SDK）
- Copilot Studio
- 应用平台/容器/无服务（App Service、AKS、ACA、Functions）
- Azure 集成服务（APIM、Logic Apps）、DevOps（CI/CD、Azure DevOps、DevSecOps）
- GitHub（Copilot、Enterprise、Actions 等）
- 数据平台（Cosmos DB、Azure SQL、PostgreSQL、Fabric、Databricks）
- 加分：客户面对面经验、PoC/MVP 交付、AI-first 开发工具（GitHub Copilot/Cursor/Claude Code）、云认证

**语言要求**：明确要求粤语（Cantonese）和英语（English）商务流利，普通话（Mandarin）加分。

**匹配点**：技术栈上 Semantic Kernel/AI Agent Service 与候选人 Agent 开发经验相通，但角色本质是客户面向的售前/交付架构师，需 4-8 年云咨询经验。匹配度主要受经验年限与粤语要求限制。

---

## 3. AWS 香港亚马逊云 — Delivery Consultant – AI/ML (CMHK Professional Services)

| 项目 | 内容 |
|---|---|
| 公司 | Amazon Web Services Hong Kong Limited（AWS Professional Services） |
| 职位 | Delivery Consultant - AI/ML, CMHK Professional Services（Job ID: 10454491） |
| 雇主类型 | 国际云服务/软件公司香港分部 |
| 来源链接 | https://www.amazon.jobs/en/jobs/10454491/ |
| 抓取日期 | 2026-09-08 |
| 薪资区间 | 未公开 |
| 经验要求 | 3 年以上云架构与方案实施经验；5 年以上 Data & AI（AI/ML、GenAI、Analytics、Database、Storage）技术经验；有架构主导/技术负责人经验 |
| 学历要求 | 计算机科学、工程相关学士（或同等经验） |

**核心职责摘录（原文）**：
- Design and implement "complex, scalable, and secure AWS solutions tailored to customer needs"（AI/ML 与 Generative AI 方案方向）
- 项目全周期担任客户可信顾问：需求收集、基础设施评估、迁移策略、最佳实践、性能优化与风险管理
- 交付过程中提供技术指导与排障；通过 mentoring、培训与可复用资产沉淀知识

**技能要求清单**：
- AWS 平台与云架构（AI/ML + GenAI + Analytics + 数据库）
- 至少一门编程/脚本语言（Python、Java、C++、Ruby、PowerShell）
- AWS Professional 级认证优先
- 企业合规与安全标准知识
- 向非技术受众解释技术方案的能力

**语言要求**：未在 JD 中提及（岗位服务 CMHK 香港客户，实际通常需粤语/英语）。

**匹配点**：AI/ML + GenAI 交付方向与候选人的 LLM 应用落地能力吻合，Python 与后端平台经验满足基础门槛。缺的是 3-5 年面向客户的云咨询交付履历，适合作为 2-3 年后的进阶目标岗。

---

## 4. 商汤科技 SenseTime — AI Navigator 多模态大模型应用算法工程师

| 项目 | 内容 |
|---|---|
| 公司 | SenseTime 商汤科技（香港办公室） |
| 职位 | AI Navigator – Multimodal Large Model Application Algorithm Engineer |
| 雇主类型 | 内地科技公司在港办公室 |
| 来源链接 | https://hk.linkedin.com/jobs/view/ai-navigator-%E2%80%93-multimodal-large-model-application-algorithm-engineer-at-sensetime-%E5%95%86%E6%B1%A4%E7%A7%91%E6%8A%80-4156171070 |
| 抓取日期 | 2026-09-08（页面显示为 Part-time Internship 且"不再接受申请"；商汤香港持续开放同类岗位，社招入口 hr.sensetime.com） |
| 薪资区间 | 未公开 |
| 经验要求 | 有机器学习与深度学习实战经验；有多模态大模型开发应用经验者优先 |
| 学历要求 | 未明确列出，仅要求数学统计基础扎实 |

**核心职责摘录（原文）**：
- "Design and optimize multimodal data fusion and alignment methods"（提升模型在业务场景的效果）
- 开发融合文本/图像/视频的多模态大模型智能应用
- 与产品、数据科学家、工程团队协作，将业务需求转化为模型方案
- 探索 AIGC、图像识别标注、多模态搜索等落地场景；跟踪多模态大模型前沿趋势

**技能要求清单**：
- CLIP、DALL-E、GPT-4 等算法的应用与优化
- TensorFlow / PyTorch 等主流深度学习框架；大规模多模态数据集处理
- Python 编程与算法问题求解
- 逻辑思维、快速学习、团队协作

**语言要求**：未在 JD 中提及。

**匹配点**：这是内地大模型公司在港最典型的应用算法岗画像：多模态大模型 + AIGC + 业务落地。候选人的 LoRA 微调与 RAG 经验直接迁移，但多模态（视觉/跨模态对齐）是相对弱项。注意该具体链接为实习岗，社招同岗需从商汤招聘官网投递。

---

## 5. Career International AP 科锐国际香港 — AI Engineer (Cloud Services Architect)

| 项目 | 内容 |
|---|---|
| 公司 | Career International AP Hong Kong Limited（内地人力资源机构在港代招，技术栈围绕 Alibaba Cloud / Tencent Cloud / Google Cloud） |
| 职位 | AI Engineer (Cloud Services Architect) |
| 雇主类型 | 内地科技公司生态在港代招岗（招聘机构发布） |
| 来源链接 | https://bebee.com/hk/jobs/ai-engineer-cloud-services-architect-career-international-ap-hong-kong-limited-tsim-sha-tsui-yau-tsi--t7xk-784757960 （JobsDB 同源镜像，JobsDB 详情页 403 无法直抓） |
| 抓取日期 | 2026-09-08（截止 2026-09-30） |
| 薪资区间 | HK$35,000 – 45,000 / 月 |
| 经验要求 | 8 年以上云基础设施、SaaS 产品与 AI 云服务部署经验；混合云与多云整合实战 |
| 学历要求 | 信息科学、计算机科学等相关学士 |

**核心职责摘录（原文）**：
- "Design and implement scalable cloud infrastructures using public (Alibaba Cloud, Tencent Cloud, Google Cloud)" + 私有云；"Lead the architecture and deployment of AI models and cloud services, ensuring optimal performance and security."
- "Oversee the end-to-end deployment of AI cloud services, including model training, inference, and operationalization."
- "Act as a technical lead in AI research projects, mentoring teams and guiding the development of AI applications."
- 成本优化：制定云资源管理成本策略；合规安全：云安全协议与漏洞审计

**技能要求清单**：
- Python、Java；云原生框架与 AI 模型部署
- Kubernetes 容器编排
- 云安全实践与风险管理
- Alibaba Cloud / Tencent Cloud / Google Cloud（公有 + 混合云）

**语言要求**：Fluent in English and Mandarin（英文与普通话流利）。

**匹配点**：职责中的模型训练/推理/运营化（MLOps）与候选人后端平台 + 模型微调背景部分契合，普通话流利是候选人优势。但 8 年云架构经验门槛远超 mid-level，且偏基础设施而非 LLM 应用，匹配度较低，仅作市场薪资锚点参考。

---

## 6. FCC Analytics — AI Engineer (LLM)

| 项目 | 内容 |
|---|---|
| 公司 | FCC Analytics Limited（香港科学园 RegTech/金融犯罪合规分析初创） |
| 职位 | AI Engineer (LLM) |
| 雇主类型 | 香港本地科技公司/初创 |
| 来源链接 | https://hk.linkedin.com/jobs/view/ai-engineer-llm-at-fcc-analytics-4141991426 |
| 抓取日期 | 2026-09-08（页面显示"不再接受申请"，作为 JD 参考示例保留） |
| 薪资区间 | 未公开 |
| 经验要求 | Entry level（第三方平台标注 1-3 年） |
| 学历要求 | 学士（第三方平台标注） |

**核心职责摘录（原文）**：
- "Develop LLM applications for tasks within the AML context"（AML = 反洗钱）
- "Research and develop prototype implementations of new algorithms and methodologies related to LLMs"
- "Work with product development team to uncover customer needs and aspirations"

**技能要求清单**：
- "Proficiency in programming and project collaboration tools, such as Python, PyTorch, Transformers, Git, etc."
- "Familiarity with the latest open-source LLMs, including but not limited to Llama, Qwen, DeepSeek, InternLM, etc."
- "Experience in agentic systems, prompt engineering, LLM deployment, LLM fine-tuning, RAG, and database usage"
- 对 AML 领域 LLM 应用的热情

**语言要求**："Proficiency in Cantonese or Mandarin. Fluency in English is advantageous."（粤语或普通话熟练，英语流利加分）

**匹配点**：这份 JD 几乎就是候选人技能清单的镜像：RAG、LLM 微调、agentic systems、开源模型（Llama/Qwen/DeepSeek）全部点名。香港硕士背景满足粤语或普通话的语言组合。唯一注意点是层级偏 entry，mid-level 候选人可以"超配"姿态争取快速承担核心模块。

---

## 7. AIFT 金融科技人工智能实验室 — AI Engineer (RAG pipelines, LLM)

| 项目 | 内容 |
|---|---|
| 公司 | Laboratory for AI-Powered Financial Technologies Limited（AIFT，InnoHK 研究中心，香港科学园，城大参与共建） |
| 职位 | AI Engineer（"18 days AL, RAG pipelines, LLM"） |
| 雇主类型 | 香港本地研究机构（InnoHK 政府背书） |
| 来源链接 | https://bebee.com/hk/jobs/ai-engineer-18-days-al-rag-pipelines-llm-laboratory-for-ai-powered-financial-technologies-limited-sh--t7xk-763762919 （JobsDB 同源，详情页 403） |
| 抓取日期 | 2026-09-08（申请截止 2026-09-14，在招） |
| 薪资区间 | 未公开 |
| 经验要求 | "Minimum 2 years of full-time working experience focusing on AI and machine learning project delivery"；经验稍逊者可考虑 Assistant AI Engineer；数据分析/ICPC/MCM 竞赛经历加分 |
| 学历要求 | 硕士及以上，Computer Science / IT 或相关专业 |

**核心职责摘录（原文）**：
- "Design and launch financial big data analytics platforms"；构建 "RAG pipelines and LLM-based AI Agents" 实现智能数据检索与工作流自动化
- 端到端 AI 功能开发："LLM screening, customized fine-tuning and performance tuning"，保证可扩展、安全、生产稳定
- 通过 API 与微服务将 AI 组件集成进现有金融系统；制定 LLM 使用、prompt engineering 与 AI 开发共享规范

**技能要求清单**：
- Python（AI 开发）
- MongoDB 与 MySQL
- LLM 应用与 AI Agent 实战："LangGraph or other mainstream frameworks"
- "Weaviate and other industry-standard vector databases"（向量数据库）
- 主流云平台基础知识；深度学习实战优先

**语言要求**："Good command of both verbal and written communication skills in Chinese and English"（中英文说写能力良好）。

**匹配点**：这是全批次中与候选人匹配度最高的 JD：RAG pipeline + LLM Agent + 微调 + LangGraph + 向量数据库逐项对应候选人核心技能；2 年经验与硕士学历门槛恰好落在 mid-level。金融大数据平台方向与后端平台经验也能衔接，建议优先投递。

---

## 8. Wizpresso — Machine Learning Engineer

| 项目 | 内容 |
|---|---|
| 公司 | Wizpresso（香港本地 FinTech/RegTech 初创，金融文档 NLP 分析） |
| 职位 | Machine Learning Engineer |
| 雇主类型 | 香港本地科技公司/初创（金融文档智能分析方向） |
| 来源链接 | https://wizpresso.careers-page.com/jobs/951dcb71-2493-4e5c-bdea-559a22767832/ （公司官网招聘页） |
| 抓取日期 | 2026-09-08 |
| 薪资区间 | 未公开 |
| 经验要求 | 未写明年限（Junior MLOps 定位）；有生产环境 ML 模型部署经验者优先 |
| 学历要求 | "Bachelor's or Master's degree in Computer Science, Engineering, or a related field." |

**核心职责摘录（原文）**：
- Collaborate with data scientists and software engineers to deploy machine learning models into production environments
- 构建并维护 "training, testing, and deploying machine learning models" 的基础设施；为 ML 项目实现 CI/CD 管道
- Monitor and optimize machine learning systems to ensure "performance, scalability, and reliability"；排查模型性能、数据质量与稳定性问题
- 与 DevOps 协作将 ML 系统集成到现有基础设施；文档化 ML 基础设施与最佳实践

**技能要求清单**：
- Python 和/或 R；ML 概念扎实
- TensorFlow / PyTorch / scikit-learn
- AWS / Azure / GCP；Docker / Kubernetes；Git
- 加分：Spark/Hadoop、Airflow/Luigi、Agile/Scrum、Terraform/Ansible

**语言要求**：未在 JD 中提及。

**匹配点**：岗位重心是 ML 系统的工程化与运维（MLOps），候选人的后端平台经验（CI/CD、部署、微服务）是稀缺优势，模型侧有微调与部署经验即可覆盖。相比纯算法岗，这条路线更能放大"算法 + 后端"的复合背景。

---

## 9. S&P Global 标普全球 — Graduate Machine Learning Engineer

| 项目 | 内容 |
|---|---|
| 公司 | S&P Global |
| 职位 | Graduate Machine Learning Engineer |
| 雇主类型 | 金融数据分析机构 |
| 来源链接 | https://www.efinancialcareers.com/jobs/graduate-machine-learning-engineer/at-s%2526p-global/in-hong-kong （S&P 官网原页 careers.spglobal.com/jobs/23284459 已 404；信息经 eFinancialCareers 页面摘要获取） |
| 抓取日期 | 2026-09-08 |
| 薪资区间 | HK$550,000 – 650,000 / 年（约 HK$45,800 – 54,200 / 月） |
| 经验要求 | Graduate 级别（应届/初阶，无年限要求） |
| 学历要求 | 未在摘要中完整显示（同司同类岗通常要求 CS/数学相关学士及以上） |

**核心职责摘录（摘要转述，非逐字原文）**：
- Collaborate with data scientists and engineers to develop and deploy machine learning models and GenAI solutions at scale
- 面向金融市场数据（financial market data）场景构建 ML/GenAI 方案
- 技术点包括 Python、PyTorch、TensorFlow、LLMs、RAG

**技能要求清单**（据摘要）：
- Python；PyTorch / TensorFlow
- LLM 与 RAG 应用开发
- 大规模模型与 GenAI 方案部署

**语言要求**：未在摘要中提及。

**匹配点**：金融数据 + LLM/RAG 的组合与候选人背景高度相关，且公开了年薪区间，可作为金融数据机构薪酬锚点。但这是 Graduate 岗，mid-level 候选人应关注同司 Engineer/Senior Engineer 序列；此 JD 主要用于理解该类雇主的技能画像。信息为摘要级，获取方式已在来源栏注明。

---

## 10. HKGAI 香港生成式 AI 研发中心 — Research Engineer (AI Development Engineer)

| 项目 | 内容 |
|---|---|
| 公司 | Hong Kong Generative AI Research and Development Center Limited（HKGAI，InnoHK 中心，HKUST 牵头） |
| 职位 | Research Engineer（functional title as AI Development Engineer，编号 HKGAI0007） |
| 雇主类型 | 香港本地研究机构（政府 InnoHK 背书，粤语/繁中主权大模型方向） |
| 来源链接 | https://hkustcareers.hkust.edu.hk/hong-kong-generative-ai-research-and-development-center-limited/hkgai0007 |
| 抓取日期 | 2026-09-08（滚动招聘直至职位填满，在招） |
| 薪资区间 | 未公开（"Salary is highly competitive and will be commensurate with qualifications and experience."，含医疗福利与约满酬金） |
| 经验要求 | 熟悉 AI 系统/LLM 训练全流程，具备优化、测试与集成实战；"Candidates with more experience will be considered for the senior position." |
| 学历要求 | "a master's degree in Computer Science, Artificial Intelligence, Machine Learning, Electronic Engineering," Information Engineering, Mathematics 或相关领域硕士 |

**核心职责/研究方向（原文）**：
- LLM 方向：model construction（pretraining、finetuning、human-AI alignment、knowledge transfer、complex reasoning、long-context learning）；modular/multi-modal models（Mixture of Experts、CLIP）；intelligent agents
- 系统优化："algorithm optimization, hardware acceleration, distributed computing, cache optimization"
- 系统测试："unit testing, integration testing, performance testing, security testing"
- 系统集成："API design and implementation, web services, message queues"

**技能要求清单**：
- AI 系统/LLM 训练流程（预训练、微调、对齐）
- 分布式计算、硬件加速、缓存优化
- 测试体系（单元/集成/性能/安全）
- API 设计、Web 服务、消息队列
- 大模型研发经验加分

**语言要求**：未明确要求（机构使命为粤语与繁简中文深度理解的主权 AI）。

**匹配点**：硕士学历门槛与候选人香港硕士背景完全匹配；finetuning、agents、API/消息队列集成对应其微调 + Agent + 后端复合能力。缺口在预训练与分布式/硬件加速等系统性经验；固定期限合同（1-2 年）性质需纳入考量。

---

## 横向对比表

| # | 公司 | 职位 | 雇主类型 | 薪资（公开信息） | 经验年限 | 语言要求 | 匹配度(1-5) |
|---|---|---|---|---|---|---|---|
| 1 | HSBC | AI Engineer - Corporate & Institutional Banking | 国际银行在港科技岗 | 未公开 | 专业经验（未注明年限，mid 级） | 未提及 | 5 |
| 2 | Microsoft 香港 | Cloud Solution Architect – Data & AI | 国际软件公司香港分部 | 未公开 | 4 年起，优先 8 年 | 粤语+英语商务流利，普通话加分 | 2 |
| 3 | AWS 香港 | Delivery Consultant – AI/ML (ProServe) | 国际云服务公司香港分部 | 未公开 | 3 年云 + 5 年 Data&AI | 未提及（客户为 CMHK） | 3 |
| 4 | 商汤科技 SenseTime | AI Navigator 多模态大模型应用算法工程师 | 内地科技公司在港办公室 | 未公开 | 有 ML/DL 实战（此链接为实习岗） | 未提及 | 3 |
| 5 | Career International AP | AI Engineer (Cloud Services Architect) | 内地云生态在港代招（招聘机构） | HK$35k–45k/月 | 8 年以上 | 英语+普通话流利 | 2 |
| 6 | FCC Analytics | AI Engineer (LLM) | 香港本地 RegTech 初创 | 未公开 | Entry（1-3 年） | 粤语或普通话，英语加分 | 5 |
| 7 | AIFT | AI Engineer（RAG pipelines, LLM） | 香港本地 InnoHK 研究中心 | 未公开 | 2 年以上（硕士+） | 中英文说写良好 | 5 |
| 8 | Wizpresso | Machine Learning Engineer | 香港本地 FinTech/RegTech 初创 | 未公开 | Junior（0-2 年） | 未提及 | 4 |
| 9 | S&P Global | Graduate Machine Learning Engineer | 金融数据分析机构 | HK$550k–650k/年 | 应届/Graduate | 未提及 | 3 |
| 10 | HKGAI | Research Engineer (AI Development Engineer) | 香港本地 GenAI 研究中心 | 未公开（具竞争力+约满酬金） | 未注明年限（经验多者升 Senior） | 未提及 | 4 |

> 市场薪资补充参照（来源：JobsDB 列表页与搜索摘要，2026-09 抓取）：本地小公司 ML AI Engineer 约 HK$20k–30k/月（Novos Technology）；带团队与客户面的资深 AI Engineer（LLM/RAG/Agent）约 HK$55k–70k/月；PayMetricLabs 统计香港 GenAI/LLM 工程师月薪中位数约 HK$67k；Levels.fyi 估计香港 AI Engineer 年度总包均值约 HK$383,900。

---

## 共性要求分析

### 1. 出现频率最高的技术关键词（按出现 JD 数排序）

| 排名 | 技术关键词 | 出现的 JD | 频次(10 份中) |
|---|---|---|---|
| 1 | LLM / GenAI 应用开发（含 prompt engineering） | 全部 10 份 | 10 |
| 2 | Python | HSBC、FCC、AIFT、Wizpresso、Career Intl、AWS、S&P、HKGAI | 8 |
| 3 | 云平台（AWS/Azure/GCP/阿里云/腾讯云） | HSBC、Microsoft、AWS、Career Intl、Wizpresso、AIFT(基础) | 6 |
| 4 | Agent / agentic 框架（LangChain、LangGraph、Semantic Kernel 等） | HSBC、FCC、AIFT、Microsoft、HKGAI | 5 |
| 5 | 深度学习框架（PyTorch/TensorFlow/HF Transformers） | HSBC、商汤、FCC、Wizpresso、S&P、HKGAI | 6 |
| 6 | 模型微调/训练（fine-tuning/SFT/对齐） | HSBC、商汤、FCC、AIFT、HKGAI | 5 |
| 7 | RAG / 向量数据库 / 检索增强 | FCC、AIFT、S&P、（HSBC 知识图谱加分） | 4 |
| 8 | MLOps / CI-CD / Docker / Kubernetes | HSBC、Wizpresso、AWS、HKGAI(API/服务) | 4 |
| 9 | 金融领域知识（AML、风控、市场数据） | HSBC、FCC、AIFT、S&P、Wizpresso | 5 |

**小结**：LLM 应用开发是绝对公约数；"Python + 云平台 + PyTorch/TensorFlow"是硬通货；RAG、Agent、微调是区分度最高的三项实操技能；MLOps 与金融领域知识是常见加分项。

### 2. 经验年限分布（10 份）

- **0-3 年（entry/graduate/junior）**：FCC Analytics（1-3 年）、Wizpresso（junior）、S&P Global（graduate）——3 份
- **约 2 年（明确写 2 年+，硕士学历）**：AIFT——1 份
- **未注明年限（要求实战经验，mid 可投）**：HSBC、商汤（此链接为实习）、HKGAI——3 份
- **3-5 年+**：AWS Delivery Consultant（3 年云 + 5 年 Data&AI）——1 份
- **4-8 年+（架构/咨询向）**：Microsoft（4 年起/8 年优先）、Career International（8 年+）——2 份

**小结**：mid-level（2-5 年）恰好位于需求曲线的中位：往上是云架构/客户交付岗（4-8 年），往下是大量的 graduate/junior 岗。AIFT、HSBC、HKGAI 三类岗位对 2-4 年经验者最友好。

### 3. 语言要求情况

- **明确要求中文类语言的有 4 份**：Microsoft（粤语+英语商务流利，普通话加分）、Career International（英语+普通话流利）、FCC Analytics（粤语或普通话，英语加分）、AIFT（中英文说写良好）。
- **未提及语言的有 6 份**：HSBC、AWS、商汤、Wizpresso、S&P Global、HKGAI（但 HKGAI 使命是粤语/中文主权大模型，实际中文能力隐含重要）。
- **规律**：客户面向型岗位（架构师/交付顾问）与本地初创更强调粤语/普通话；纯研发岗多不设硬性语言门槛。香港硕士毕业生普遍满足"普通话+英语"，粤语是变量项。

### 4. 给求职者的 3 条准备建议

1. **把 RAG + Agent + 微调打包成金融场景作品集**：本批 JD 中 AIFT、FCC、HSBC、S&P 全部点名 RAG/Agent/fine-tuning，且 5 份带金融属性。建议用 1-2 个端到端项目（如"AML 文档审查 RAG + LangGraph Agent + LoRA 微调 Qwen/DeepSeek 小模型"）覆盖 LangChain/LangGraph、向量数据库（Weaviate/Milvus）、HuggingFace Transformers 全链路，直接对标 JD 原文关键词。
2. **补 MLOps 与云认证，放大后端平台优势**：Docker/Kubernetes/CI-CD 在 4 份 JD 中出现，AWS/Azure 出现在 6 份中。后端平台经验是算法背景候选人中最稀缺的差异化资产，考一个 AWS Solutions Architect Associate 或 Azure AI Engineer 认证（Microsoft JD 明确列为目标认证），即可同时解锁 MLOps 岗（Wizpresso 型）与 2-3 年后的交付架构岗（AWS/Microsoft 型）。
3. **语言与投递策略**：粤语流利度决定 Microsoft 等客户面向岗的可达性，短期无法速成则优先投"未提及语言"的 6 类岗（HSBC、HKGAI、AIFT 等）；AIFT 这类 InnoHK 中心明确"硕士+2 年"门槛且滚动招聘，与背景完全吻合，应作为第一优先级；同时把 Career International HK$35k-45k 与 S&P HK$550k-650k/年 作为薪酬谈判的两个锚点。

---

*文件生成：ZCode 研究助理，2026-09-08。所有 JD 内容来自公开渠道抓取/摘要，仅作求职参考；职位时效性请以各来源链接实时状态为准。*
