# 中国内地算法工程师赴香港工作 — 市场、薪资、面试、签证调研笔记

> 调研日期：2026-09-08。检索工具：WebSearch + WebFetch / web_reader（官方页面为入境事务处 immd.gov.hk，抓取于 2026-09）。
>
> **一句话结论**：香港 AI/LLM 算法岗供给在 2025-2026 年快速扩张（AI 岗位发布量同比 +50%，JobsDB 上 AI 相关岗位约 1,500-1,600 个），对"平台/后端 + RAG + 后训练 + Agent"画像的内地工程师匹配度较高；月薪中位约 HK$4-6.5 万（量化 2-4 倍于此），面试以英语进行、考察 LeetCode + ML/LLM 基础 + 项目深挖；最现实的签证路径是**高才通 A 类（若年薪达标）或专才 GEP（雇主担保）**，注意高才通 B/C 类对内地居民有"海外居留/永久居民身份"前置门槛；工作强度总体低于内地大厂 996（银行科技/初创尤甚，投行前台和量化除外）；香港无年龄歧视立法但 IT 业缺人，35-40 岁压力显著小于内地。

---

## 1. 岗位供给与主要雇主

### 总量级
- **JobsDB**（香港最大求职平台）2026 年 9 月显示约 **1,590 个 "Artificial Intelligence" 岗位**，其中"算法工程师"约 1,100+ 个；另有专门 LLM 岗位列表页（"Build, optimize, and scale production-grade LLM systems and RAG pipelines"）。Indeed HK 有 100+ LLM 相关岗位，Glassdoor HK 约 79 个 LLM engineer 岗位。
  来源：[JobsDB Artificial Intelligence Jobs（2026-09）](https://hk.jobsdb.com/artificial-intelligence-jobs)、[JobsDB LLM Jobs](https://hk.jobsdb.com/llm-jobs/in-Hong-Kong-SAR)、[Indeed HK LLM jobs](https://hk.indeed.com/q-llm-jobs.html)
- **PwC 香港 AI Jobs Barometer**：2024→2025 年 AI 相关岗位发布量**同比 +50%**，占总岗位比例从 3.6% 升至 4.7%，TMT 行业领涨（新闻稿日期约 2026-07）。
  来源：[PwC HK 新闻稿](https://www.pwchk.com/en/press-room/press-releases/pr-140726.html)、[PwC 2025 Global AI Jobs Barometer（HK PDF）](https://www.pwccn.com/en/issues/global-ai-jobs-barometer-jun2025.pdf)
- **Hays 香港**：传统软件开发岗位发布量在亚洲跌幅最大（约 -90%），需求向 Data & Advanced Analytics、AI 项目转型——即"普通码农岗收缩、AI/数据岗扩张"的结构性变化。
  来源：[Hays HK press release](https://www.hays.com.hk/press-release/content/hong-kong-sar-sees-shift-in-tech-hiring-90-per-cent-decline-in-software-development-roles-highest-percentage-in-asia)
- **人才池**：HKUST CBSA 报告估计香港 AI 人才池 2024 年约 **23,600 人**（较 2015 年 +280%），但存在三类人才错配。
  来源：[HKUST CBSA](https://cbsa.hkust.edu.hk/events/cbsa-releases-report-hong-kong-ai-talent-market-highlighting-three-types-mismatches)
- 内地招聘平台也有香港专区：BOSS直聘香港算法工程师（含"RAG/LLM 开发和部署经验"中级岗，1-2 年经验，部分公司写明"将提供并支付优才/高才"费用）；猎聘香港算法开发 10,000+ 条（含重复/驻港岗位）。
  来源：[BOSS直聘香港算法工程师](https://www.zhipin.com/zhaopin/59e07a83f46d589403x729W1/)、[猎聘](https://www.liepin.com/city-hongkong/career/suanfakaifa/)

### 分雇主类型
| 雇主类型 | 代表 | 观察 |
|---|---|---|
| 银行 | HSBC、渣打、中银香港、恒生 | 长期招聘 ML/AI/data 岗；HSBC 香港在 Glassdoor 有 647 条面试记录，招聘体量大但流程慢 |
| 量化/对冲基金 | Jane Street、Citadel/Citadel Securities、Millennium、Two Sigma、HFT 机构 | eFinancialCareers 列表显示香港有数百个 ML quant 岗（一说 586 个 ML quant researcher 岗位在招）；薪酬最高但门槛也最高 |
| 本地 AI 初创/园区 | 数码港（Cyberport）500+ AI 与数据科学初创、OPC Hub（GenAI/Agent 方向）、HKSTP 科技园 | 数码港 2025 年 3 月招聘博览提供 2,500+ 职位；生态以 GenAI、Agent、区块链为主 |
| InnoHK/HKGAI 生态 | 香港生成式人工智能研发中心 HKGAI（港科大牵头、郭毅可领导，InnoHK 成员，发布 HKGAI V1/V3 大模型） | 有实习与研发岗发布（Offertoday 上有数据分析/法务实习等），正式研发岗多走港科大招聘渠道 |
| 内地大厂驻港 | 字节（已迁至中环 IFC）、阿里、小红书（铜锣湾时代广场"内地大厂一条街"）、腾讯、TCL 香港研研究院、Apple HK | 证券时报 2025 年报道：香港重点办累计签约 102 家企业、内地企业占比超 60%，香港 AI 产业 2025 年产值超 380 亿港元（+45%）；腾讯 2027 校招 AI 岗工作地点覆盖香港；TCL HK 招 LLM Engineer (Data & Optimization)、Apple HK 招 LLM Efficiency 研究岗 |
| 大学/研究岗 | 港科大、港大、中大、港城大等 | AI 教研岗常年开放，但多要求博士与论文 |
| 保险公司 | 友邦/保诚等有数据科学团队 | **未找到可靠的 AI 算法岗招聘量级公开数据**，存疑 |

来源：[数码港 AI 生态](https://www.cyberport.hk/zh-cn/digital_tech/ai/)、[数码港招聘博览（青年就业网络，2025-02）](https://yen.hkfyg.org.hk/2025/02/13/)、[HKGAI 官网](https://www.hkgai.info/contact)、[InnoHK 介绍页](https://www.innohk.gov.hk/zh-cn/r-d-centres/air-innohk/)、[证券时报"内地大厂一条街"实探](https://stcn.com/article/detail/3428016.html)、[eFinancialCareers 香港 quant 岗汇总（quantt.co.uk 转述）](https://www.quantt.co.uk/quant-finance-jobs/hong-kong)、[第一财经：大厂 AI 校招](https://www.yicai.com/news/102560299.html)

**量级判断**：全港 AI/LLM 方向在招岗位约 1,500-2,000 个（JobsDB 口径），叠加 LinkedIn/猎聘/猎头渠道估计总需求数千人级别；相对内地动辄数万的大厂算法岗，池子小一个数量级，但竞争者基数也小，且 2025-2026 处于扩张期。

## 2. 薪资水平（HKD）

### 通用市场口径（2025-2026 薪资指南/聚合器）
| 来源 | 口径 | 数字 |
|---|---|---|
| JobsDB（2026-09） | ML Engineer 月薪均值 | HK$34K-40K；岗位发布区间常见 HK$20-30K 至 HK$40-60K（[来源](https://hk.jobsdb.com/career-advice/role/machine-learning-engineer/salary)） |
| JobsDB | AI Engineer 月薪均值 | HK$33K-38K（[来源](https://hk.jobsdb.com/career-advice/role/artificial-intelligence-engineer/salary)） |
| CTgoodjobs | ML 岗月薪 | 最低 HK$25K / 中位 HK$27.5K / 最高 HK$50K（经搜索摘要转述） |
| **Morgan McKinley 2026 香港科技薪资指南** | 月薪 Low/Median/High | **ML Engineer 35K/65K/90K；Algorithm Engineer 30K/50K/75K；Data Scientist 30K/50K/80K；MLOps 40K/55K/75K**；IT 应届生 20-26K；跳槽涨薪约 15%（低于高峰期 20%+）；ML 与云架构是为数不多有薪资溢价的岗位（[来源](https://www.morganmckinley.com/hk/salary-guide/technology/permanent-salaries)，2026-09 抓取） |
| Levels.fyi | ML/AI 软件工程师年总包中位 | 约 HK$61 万-71 万（含股票/奖金，样本偏国际科技公司）（[来源](https://www.levels.fyi/t/software-engineer/focus/ml-ai/locations/hong-kong-hkg)） |
| Robert Half 2026 香港薪资指南 | AI Engineer 年薪 | HK$60 万-144 万（25 分位 60 万）（[来源](https://www.roberthalf.com/hk/en/insights/salary-guide)，转述） |
| 一手分享（知乎，约 2023） | 内地赴港程序员 | 应届 18-20K，2-4 年升 senior 25-30K，政府/金融机构岗 40-50K（数字偏旧，仅作下限参考）（[来源](https://zhuanlan.zhihu.com/p/606766311)） |

### 分雇主类型（对该画像 5-8 年经验的合理区间，年总包估算）
- **银行（HSBC/渣打/中银）**：约 HK$60 万-120 万/年（月薪 4-8 万 + 花红 1-3 个月）。Robert Half AI Engineer 区间下沿与 Morgan McKinley 中位数交叉印证。
- **本地初创/数码港企业**：月薪约 HK$35K-65K，年包 45-90 万，现金为主、期权价值不确定。**无系统性公开数据，此为 JD 与招聘指南推断**。
- **内地大厂驻港（字节/腾讯/阿里国际）**：参考字节大模型算法工程师"70-100K·15 薪"（内地口径），驻港岗位总包大致对标或略高于内地同级，年包 100 万-200 万人民币量级；**香港办公室具体薪资未找到系统公开数据**。
  来源：[字节跳动招聘官网](https://jobs.bytedance.com/)、[第一财经](https://www.yicai.com/news/102560299.html)
- **量化/对冲基金**：明显高于其他雇主。毕业生 HK$50-80 万起；ML quant researcher 岗位挂牌 HK$150 万-250 万；HFT quant researcher 可达 HK$230 万-400 万；资深可超 HK$300 万。
  来源：[quantt.co.uk 香港 quant 薪资页](https://www.quantt.co.uk/quant-finance-jobs/hong-kong)、eFinancialCareers 挂牌数据（转述）

**结论**：该画像（5-8 年、LLM 平台/RAG/微调/Agent）在香港的合理预期是**月薪 HK$5-8 万、年总包 70-120 万港币**（银行/大厂驻港口径）；量化的 ML researcher 岗可达 150 万+ 但通常要求更强的数学/研究背景。

## 3. 面试考察重点（按雇主类型）

### 银行（HSBC / 渣打 / 中银香港）
- 流程：在线测评（行为/性格问卷）→ 1-2 轮编程测评 → 视频面/技术面 → HR 面，全程约 3-5 周。
- 考察：Python/Java、数据结构与算法（LeetCode 中等题，如 longest palindromic substring、container with most water、best time to buy and sell stock）、ML 基础（监督/无监督、过拟合、推荐系统原理）、行为面（简历深挖、困难与解决）。
- 真实案例：Jointaro 上一份 2024-10 香港地区 HSBC ML Engineer 经历——**挂在最早的 HR 性格问卷阶段**，说明银行流程前置于技术、且对 soft skills 筛选严格。
- 来源：[Dataford HSBC ML Engineer 面试指南（2026）](https://dataford.io/interview-guides/hsbc/machine-learning-engineer)、[Jointaro HSBC HK 面经（2024-10）](https://www.jointaro.com/interviews/companies/hsbc/experiences/machine-learning-engineer-hong-kong-october-17-2024-no-offer-neutral-0134e876/)、[Glassdoor HSBC HK 面试题汇总](https://www.glassdoor.com/Interview/HSBC-Hong-Kong-Interview-Questions-EI_IE3482.0,4_IL.5,14_IC2308631.htm)、[Glassdoor 渣打 SWE 面试题](https://www.glassdoor.com/Interview/Standard-Chartered-Bank-Software-Engineer-Interview-Questions-EI_IE226853.0,23_KO24,41.htm)、[AmbitionBox 渣打 DS 面试题](https://www.ambitionbox.com/interviews/standard-chartered-interview-questions/data-scientist)

### 量化基金
- Jane Street：概率/数学/思维题为主，多小问递进，官方明确**不考金融与经济知识**，考察协作式解题与对犯错的反应；Citadel：45-60 分钟技术+行为。ML researcher 岗另考 ML 深度与（部分）编程（Python/算法）。
- 来源：[Jane Street 官方 Interviewing 页](https://www.janestreet.com/join-jane-street/interviewing/)、[Citadel Securities 官方流程说明](https://www.citadelsecurities.com/careers/career-perspectives/our-quantitative-research-interview-process/)、[eFinancialCareers：JS/Jump/Citadel 真题](https://www.efinancialcareers.com/news/electronic-trading-interviews)、[Reddit r/quantfinance JS quant research 终面实录](https://www.reddit.com/r/quantfinance/comments/1qot1o5/jane_street_quant_research_final_round_interview/)
- 注意：**香港办公室专属面经很少**，多为 firm-wide 流程；一亩三分地上香港相关面经以银行（如 GPB 环球私人银行 JSA）与内地大厂为主。来源：[一亩三分地中国面经标签](https://www.1point3acres.com/bbs/tag/%E4%B8%AD%E5%9B%BD%E9%9D%A2%E7%BB%8F-22-88.html)

### 内地大厂驻港（字节/腾讯等）与 Agent 岗
- 面试风格与内地一致：项目深挖 + coding + 大模型八股。牛客热榜显示 2025-09 字节 Agent 开发岗一面居热榜第 3；典型问题：项目实现细节深挖、"大模型输出不符合预期如何处理"、代码执行安全、奖励函数坍缩、离线/在线 RL。
- 来源：[牛客字节校招面经页](https://www.nowcoder.com/enterprise/665/interview)、[字节 Agent 开发一面面经](https://www.nowcoder.com/feed/main/detail/d34ec2281429417eb546f160f181cdfa)、[字节大模型算法岗面经](https://www.nowcoder.com/discuss/921942180380299264)

### 语言
- 力扣讨论区（香港 IT 求职总结）：**面试语言基本是英语，其次粤语，普通话较少用**；量化岗普遍有笔试。内地背景公司（字节/中资机构）可用普通话，但英语自我介绍与技术表达是硬要求。
- 来源：[力扣讨论：香港 IT 技术栈与面试](https://leetcode.cn/circle/discuss/cddG77/)

## 4. 入职后主要工作内容（JD 与在职分享提炼）

- 生产级 LLM 系统与 **RAG pipeline** 的搭建、优化与规模化（JobsDB LLM 岗 JD 原文）；垂直领域大模型的训练/**SFT 微调**与部署；LLM 应用与生成式 AI 方案开发；用公开与内部数据集做模型评估；AI 应用全生命周期开发。来源：[JobsDB LLM Jobs](https://hk.jobsdb.com/llm-jobs/in-Hong-Kong-SAR)、[Indeed HK LLM jobs](https://hk.indeed.com/q-llm-jobs.html)
- 银行侧：AI 平台的设计/开发/部署（渣打 AI Ops Engineer JD）、内部 AI 工具与合规场景落地。来源：[渣打 AI Ops Engineer JD（LinkedIn）](https://cn.linkedin.com/jobs/view/ai-ops-engineer-at-standard-chartered-4386860095)
- 大厂驻港：国际化业务的推荐/LLM 算法（字节国际电商大模型算法工程师等）。来源：[字节招聘官网](https://jobs.bytedance.com/campus/m/position/detail/7667568479647287557)
- 在职者分享（知乎内地程序员赴港五年）：香港 IT 岗位以**交付与维护为主**，一人多角色、节奏平稳，非内地式" relentless 冲刺"；氛围自由、午餐两小时、加班少于内地。来源：[知乎：从内地被辞退后我到香港做了五年程序员](https://zhuanlan.zhihu.com/p/606766311)
- 与该画像的差异提醒：香港 JD 常要求端到端"平台 + 模型 + 上线 + 运维"通吃，内部平台/RAG 经验直接对口；纯研究型 Agent 算法岗（如 post-training/RL）多集中在量化基金、大模型团队与高校，岗位少、门槛高。

## 5. 需要补齐的能力（针对该画像）

1. **英语口语/面试表达**：面试与技术交流默认英语（力扣讨论、HSBC 流程佐证）；能读写不够，需练英文项目讲述与 behavioral。粤语不是多数 JD 的硬门槛（"流利中文，粤语更佳"是常见写法），但本地客户向岗位与部分本地公司明确要求粤语。来源：[BOSS直聘香港 JD 示例](https://www.zhipin.com/zhaopin/59e07a83f46d589403x729W1/)
2. **LeetCode**：所有雇主类型都有编程环节（银行中等题、量化概率+算法、大厂风格不变）。
3. **LLM/Agent 系统设计**：RAG 评测、Agent 评测、输出不可控处理、成本/延迟权衡是 JD 与面经高频点；该画像已有实操，建议补系统化方法论。
4. **量化方向额外要求**：概率与数学题、（如做 ML researcher）研究深度与金融数据直觉；不考金融知识本身（Jane Street 官方口径）。
5. **签证不是能力问题而是材料问题**：见第 6 节；BOSS直聘多个香港 JD 写明雇主支付优才/高才费用，说明雇主配合担保/办身份较常见。
6. **薪酬谈判与格式**：香港习惯写 expected salary、notice period；猎头（Michael Page/Morgan McKinley/Robert Walters）是银行与初创的主要渠道。

## 6. 签证路径（官方信息，immd.gov.hk，2026-09 抓取）

> **2026-09-08 更新**：本人为香港院校 2025-10 毕业生，**已持 IANG 签证（至 2028-01）**——上表 GEP/TTPS 的适配度分析已被取代。IANG 官方规则（immd.gov.hk/eng/services/visas/IANG.html，2026-04 版）：首签 24 个月无就业条件；续签需已获学位级别、市场薪酬的工作，按 3+3 年模式；期内自由换工作无需批准；学生签证期间计入 7 年永居居住。对求职的直接含义：**雇主零担保成本、随时到岗**，这本身就是对香港雇主的差异化优势。执行计划见 [hk-3-month-job-hunt-plan.md](hk-3-month-job-hunt-plan.md)。

| 计划 | 核心门槛 | 首签/续签 | 对该画像适配度 |
|---|---|---|---|
| **高才通 TTPS A 类** | 申请前一年年收入 ≥ HK$250 万（应纳税雇佣/经营收入） | 首签 36 个月；续签需证明在港就业或经营（标准续签最长 3 年）；住满 2 年且年薪 ≥ HK$200 万可走"顶尖人才"续 6 年 | 若年薪折算达标（约人民币 230 万+）则是**最优解**：无需雇主、自由换工作 |
| **高才通 B 类** | 过去 5 年内 3 年工作经验 + 合资格大学（THE/QS/U.S.News/软科百强或内地 Top20）毕业 | 首签 24 个月 | **注意硬门槛：中国内地居民申请 B/C 类须持海外永久居民身份，或在申请前已在海外连续居住至少 1 年**（官方页明确）；纯内地履历者不适用 |
| **高才通 C 类** | 百强院校毕业 5 年内、经验不足 3 年 | 首签 24 个月，年度配额先到先得 | 该画像经验超标，不适用；且同样受内地居民限制 |
| **专才 GEP/ASMTP** | 须有香港雇主 offer + 真实空缺 + 本地难以填补 + 薪酬大致对标市场；无配额无行业限制 | 首签 36 个月（或合同期较短者）；续签"3+2"；换雇主须入境处事先批准；住满 2 年且年薪 ≥ HK$200 万可续 5 年；**7 年连续通常居住可申请永居** | **对该画像最现实**：拿到香港 offer 后由雇主配合办理，通过率高、周期约 4-6 周（官方 2-3 周处理 + 备料） |
| **优才 QMAS** | 无需 offer；2026 年起改为 **12 项准则须满足至少 6 项**的资格制（取代旧 245 分综合计分制；官方页现为"General Points Test — 12 assessment criteria"）；2023-10 起暂停年度配额（两年期，2026 年是否恢复以官方为准） | 首签 36 个月；续签 3+2；顶尖收入者续 5 年；7 年可申永居 | 备选：若无法立即拿到 offer 可先申请身份再求职；配额与细则变动风险较高，以 [官方页](https://www.immd.gov.hk/eng/services/visas/quality_migrant_admission_scheme.html) 为准 |

- 2026 年高才通续签收紧（二手来源，供参考）：2026-01-30 起续签前须完成入境处"专属问卷调查"；2026-08-19 系统升级后合同期限、强积金 MPF、持股比例、学历认证等材料必填；审核聚焦"在港受雇获稳定收入或实质参与本地业务"，存款/房产不计入。来源：[gov.hk 高才通续签指引](https://www.gov.hk/sc/residents/immigration/nonpermanent/applyextensionstay/TTPSentrants.htm)、[知乎：2026 续签新政解析](https://zhuanlan.zhihu.com/p/2032161944845673877)、[知乎：2026-08 续签审核要点](https://zhuanlan.zhihu.com/p/2071189850431214004)
- **官方链接**：[TTPS](https://www.immd.gov.hk/eng/services/visas/TTPS.html) / [ASMTP 专才](https://www.immd.gov.hk/eng/services/visas/ASMTP.html) / [QMAS 优才](https://www.immd.gov.hk/eng/services/visas/quality_migrant_admission_scheme.html) / [人才清单 talent.gov.hk](https://www.talent.gov.hk)
- **拿身份节奏**：任一途径 7 年通常居住即可申请香港永居；即从入职当天起算约 7 年。首签获批时间：高才通约数周、专才约 4 周量级（官方称处理约 2-3 周）。

## 7. 工作强度与 996 对比

- **宏观**：香港每周平均工时约 50.1 小时，高于全球均值 38%，被称为"全球最累城市"之一；26 万+雇员每周 56 小时以上，近 5 万人达 72 小时以上；**香港无标准工时立法**。来源：[经济导报：香港加班文化](https://www.jdonline.com.hk/content_71652.html)、[经济导报：996都是奢望](https://www.jdonline.com.hk/content_57352.html)、[HK01/Kisi 排名](https://www.hk01.com/%E7%A0%94%E7%A9%B6%E6%89%80/552918)
- **分行业**：投行 IBD 分析师 90-140 小时/周（全球最重，香港尤甚）；金融服务业整体 >50 小时/周；**中资银行 IT 相对规律（约朝九晚八，8 点下班属常态、10 点算加班）**；普通 IT/科技岗通常 45-60 小时。来源：[Voyage Career 港新投行对比](https://www.voyagecareer.com/blog/banker-8026294d-1689-4eea-8954-a0d40eaf8f00)、[Yahoo财经香港](https://hk.finance.yahoo.com/news/%E5%81%9A%E9%87%91%E8%9E%8D%E6%9C%8D%E5%8B%99%E6%A5%AD%E6%AF%8F%E9%80%B1%E5%B7%A5%E4%BD%9C%E5%A4%9A%E6%96%BC50-1%E5%B0%8F%E6%99%82-3%E5%80%8B%E6%96%B9%E6%B3%95%E5%B9%B3%E8%A1%A1%E7%94%9F%E6%B4%BB-095048084.html)、[eFinancialCareers：香港中资银行工时](https://www.efinancialcareers.hk/news/2019/02/easy-hours-chinese-banks)
- **一手对比**：内地赴港程序员自述——香港职场"没有内地那么内卷"，午餐两小时、加班明显少于 996，身体状态好转。来源：[知乎：为什么选择去香港工作（IT）](https://zhuanlan.zhihu.com/p/461992337)、[知乎：从内地被辞退后我到香港做了五年程序员](https://zhuanlan.zhihu.com/p/606766311)
- **量化基金**：无系统公开工时数据；业界共识是强度高于银行、接近或略低于内地大厂冲刺期。**Glassdoor 分雇主 WLB 评分未逐家核实，属信息缺口。**
- **结论**：对"银行科技/初创/大厂驻港技术岗"，实际体感普遍好于内地 996（72 小时/周制度化加班）；投行前台与量化核心岗例外。

## 8. 35 岁+ 稳定性与年龄问题

- **法律**：香港四条反歧视条例（性别、残疾、家庭岗位、种族）**均不涵盖年龄**；雇佣中的年龄歧视仅有劳工处《消除雇佣年龄歧视实务指引》，无强制力。来源：[平等机会委员会 EOC](https://www.eoc.org.hk/en/discrimination-laws/what-you-should-know-under-hong-kong-s-anti-discrimination-ordinances)、[Tanner De Witt 律所概述](https://www.tannerdewitt.com/zh-hans/insight-and-news/overview-of-anti-discrimination-laws-in-hong-kong/)、[劳工处实务指引 PDF](https://www.labour.gov.hk/eng/plan/pdf/eade/Employers/PracticalGuidelines.pdf)
- **现实**：香港 IT 人才短缺，"35 岁危机"远弱于内地；知乎一手分享称 35 岁程序员在香港仍被视为"盛年"，赴港被视为规避内地 35 岁门槛的路径之一（内地背景：见[35岁门槛-维基百科](https://zh.wikipedia.org/zh-cn/35%E5%B2%81%E9%97%A8%E6%A7%A0)、[BBC 中文 35 岁现象报道](https://www.bbc.com/zhongwen/simp/chinese-news-69236750)）。来源：[知乎：从内地被辞退后我到香港做了五年程序员](https://zhuanlan.zhihu.com/p/606766311)、[Tecky Academy：程序员三十岁要转行是迷思](https://tecky.io/zh_Hant/blog/%E7%A0%B4%E9%99%A4%E8%BF%B7%E6%80%9D%E7%B3%BB%E5%88%97-programmer-%E5%81%9A%E5%88%B0%E4%B8%89%E5%8D%81%E6%AD%B2%E5%B0%B1%E8%A6%81%E8%BD%89%E8%A1%8C/)
- **反面证据**：40-50 岁香港本地 IT 管理层失业后难再就业的真实案例存在（40 岁银行 IT 失业 8 个月、50 岁 IT 经理月入 6 万失业案例），说明高龄+高薪岗位风险仍在，只是门槛比内地晚约 5-10 年。来源：[YouTube：40歲銀行IT失業8個月](https://www.youtube.com/watch?v=949P3iOc7vc)、[LinkedIn/ISSI 香港中年 IT 从业员案例](https://cn.linkedin.com/posts/issihkcom_%E4%BB%A5%E4%B8%8B%E6%98%AF%E6%A0%B9%E6%93%9A%E9%A6%99%E6%B8%AF%E8%BF%91%E5%B9%B4%E7%9C%9F%E5%AF%A6%E4%B8%AD%E5%B9%B4IT%E5%BE%9E%E6%A5%AD%E5%93%A1%E5%A4%B1%E6%A5%AD%E6%A1%88%E4%BE%8B)
- **裁员**：2023-2024 金融业（HSBC 等）有结构性裁员报道，但 2025 年起香港 AI 岗需求扩张（PwC 数据）；**2025-2026 香港科技公司裁员量的系统统计未找到可靠公开数据**。
- **结论**：对该画像（约 32-38 岁），香港的风险敞口明显小于内地：无法定年龄歧视但也没有法律保护，实际门槛更多来自薪资预期与技能迭代；7 年永居路径提供长期确定性。

---

## 信息缺口（未找到可靠公开数据）

1. **保险公司（AIA/保诚等）AI 算法岗**的招聘量级与薪资：仅有间接证据，未找到系统数据。
2. **内地大厂香港办公室（字节/腾讯/阿里 HK）算法岗的薪酬带宽**：只有内地口径与个别 JD，无香港专列数据（Levels.fyi 香港样本量小）。
3. **量化基金香港办公室 ML researcher 的本地化面经**：只有 firm-wide 流程与真题，缺香港区具体轮次细节。
4. **香港初创/数码港企业薪资中位数**：无权威统计，仅招聘指南与零散 JD。
5. **Glassdoor 各雇主（如 Citadel HK、字节 HK）的 work-life balance 评分**：未逐家抓取核实。
6. **优才 QMAS 2026 年是否恢复年度配额**：官方页面未列明，二手来源说法不一。
7. **香港 2025-2026 科技/金融裁员量系统统计**：无权威年度数据。
8. 一亩三分地/牛客上**"香港算法岗"面经数量有限**，面试考察结论部分依赖银行类岗位与内地大厂面经的外推，已注明。

## 主要来源清单（部分）

- 官方：[immd.gov.hk TTPS](https://www.immd.gov.hk/eng/services/visas/TTPS.html) · [ASMTP](https://www.immd.gov.hk/eng/services/visas/ASMTP.html) · [QMAS](https://www.immd.gov.hk/eng/services/visas/quality_migrant_admission_scheme.html) · [gov.hk 续签](https://www.gov.hk/sc/residents/immigration/nonpermanent/applyextensionstay/TTPSentrants.htm) · [EOC](https://www.eoc.org.hk/en/discrimination-laws/what-you-should-know-under-hong-kong-s-anti-discrimination-ordinances) · [劳工处年龄歧视指引](https://www.labour.gov.hk/eng/plan/pdf/eade/Employers/PracticalGuidelines.pdf)
- 薪资：[Morgan McKinley 2026 HK 科技薪资](https://www.morganmckinley.com/hk/salary-guide/technology/permanent-salaries) · [JobsDB ML salary](https://hk.jobsdb.com/career-advice/role/machine-learning-engineer/salary) · [Levels.fyi HK](https://www.levels.fyi/t/software-engineer/focus/ml-ai/locations/hong-kong-hkg) · [Robert Half 2026](https://www.roberthalf.com/hk/en/insights/salary-guide) · [quantt.co.uk](https://www.quantt.co.uk/quant-finance-jobs/hong-kong) · [Michael Page 2026](https://www.michaelpage.com.hk/salary-guide)
- 市场与雇主：[PwC HK AI Jobs Barometer](https://www.pwchk.com/en/press-room/press-releases/pr-140726.html) · [Hays HK](https://www.hays.com.hk/press-release/content/hong-kong-sar-sees-shift-in-tech-hiring-90-per-cent-decline-in-software-development-roles-highest-percentage-in-asia) · [HKUST CBSA](https://cbsa.hkust.edu.hk/events/cbsa-releases-report-hong-kong-ai-talent-market-highlighting-three-types-mismatches) · [证券时报](https://stcn.com/article/detail/3428016.html) · [数码港 AI](https://www.cyberport.hk/zh-cn/digital_tech/ai/) · [HKGAI](https://www.hkgai.info/contact)
- 面经：[Jointaro HSBC HK](https://www.jointaro.com/interviews/companies/hsbc/experiences/machine-learning-engineer-hong-kong-october-17-2024-no-offer-neutral-0134e876/) · [Dataford HSBC](https://dataford.io/interview-guides/hsbc/machine-learning-engineer) · [Glassdoor HSBC HK](https://www.glassdoor.com/Interview/HSBC-Hong-Kong-Interview-Questions-EI_IE3482.0,4_IL.5,14_IC2308631.htm) · [Jane Street](https://www.janestreet.com/join-jane-street/interviewing/) · [牛客字节面经](https://www.nowcoder.com/enterprise/665/interview) · [一亩三分地](https://www.1point3acres.com/bbs/tag/%E4%B8%AD%E5%9B%BD%E9%9D%A2%E7%BB%8F-22-88.html) · [力扣香港求职讨论](https://leetcode.cn/circle/discuss/cddG77/)
- 文化/年龄：[经济导报](https://www.jdonline.com.hk/content_71652.html) · [知乎赴港五年程序员](https://zhuanlan.zhihu.com/p/606766311) · [知乎赴港 IT 一年](https://zhuanlan.zhihu.com/p/461992337) · [Tecky Academy](https://tecky.io/zh_Hant/blog/%E7%A0%B4%E9%99%A4%E8%BF%B7%E6%80%9D%E7%B3%BB%E5%88%97-programmer-%E5%81%9A%E5%88%B0%E4%B8%89%E5%8D%81%E6%AD%B2%E5%B0%B1%E8%A6%81%E8%BD%89%E8%A1%8C/) · [BBC 中文 35 岁现象](https://www.bbc.com/zhongwen/simp/chinese-news-69236750)
