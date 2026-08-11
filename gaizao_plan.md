# MODULAR-RAG-MCP-SERVER 改造设计方案（详细版）

> 状态：**待评审**（未开始实施）
> 读者：算法工程师
> 目标：让本项目成为一个**更完整、覆盖全部算法工作、可在全新环境完整复现、且为 Agentic RAG 预留扩展**的企业级 RAG 系统。

---

## 1. 背景与目标

### 1.1 现状问题（读码核实）

| # | 问题 | 证据 |
|---|---|---|
| 1 | **无法在新环境复现** | [pyproject.toml](pyproject.toml) 依赖全部 `>=` 无锁文件；`requires-python = ">=3.10"` |
| 2 | **真实 API Key 明文入库** | [config/settings.yaml](config/settings.yaml) llm/embedding/vision 三处 `sk-ws-...`，被 git 跟踪且未被 .gitignore 忽略 |
| 3 | **纯检索，无问答生成** | `query_knowledge_hub` 是检索-only；`BaseLLM` 只用于 rerank/摄取，不生成答案 |
| 4 | **评测指标失真** | [golden_test_set.json](tests/fixtures/golden_test_set.json) 的 `expected_chunk_ids`/`expected_sources` 全为空 → hit_rate/mrr 恒为 0 |
| 5 | **入口是桩** | [main.py](main.py) 只 print 后返回 0；`mcp-server` 控制台脚本并不真正启动服务器 |
| 6 | **无自检/引导/版本锁定** | 无 bootstrap、无 self_check、无 `.python-version` |
| 7 | **数据更新有孤儿 chunk bug** | BM25 `remove_document` 按内容 hash 前缀匹配，chunk_id 前缀是 source_path hash → 内容变更重摄留下孤儿（Phase 4 处理） |

### 1.2 目标

1. **可复现**：全新环境 `git clone → 一条命令 bootstrap → 可运行、有数据、可自检`；锁定 Python 3.12 + uv.lock。
2. **密钥治理**：真实 key 停止入库、环境变量优先、提供脱敏模板。
3. **完整性**：覆盖算法全链路（检索 → 生成 → 评测 → 数据版本 → Agentic 扩展），分阶段补齐。
4. **Agentic 可扩展**：为 Agent 化能力（工具调用、路由、记忆、反射）预留与既有约定一致的扩展缝隙。

### 1.3 非目标（本次不做）

- 删除 git 历史中的 key（独立事项，用户自行轮换）
- Docker 化、K8s、多租户、RBAC（企业部署阶段再议）
- 重写现有核心检索链路（保持稳定，只加扩展）

---

## 2. 总体架构与设计原则

### 2.1 现有分层

```
src/libs/            可插拔 provider 库（LLM/Embedding/VectorStore/Reranker/Splitter/Evaluator）
src/core/            query_engine / response / trace / settings / types
src/ingestion/       pipeline / document_manager / storage / transform
src/mcp_server/      protocol_handler + tools（MCP 服务器）
src/observability/   logger / trace collector / dashboard / evaluation
scripts/             命令行入口（ingest / query / evaluate / start_dashboard）
data/                本地内嵌存储（ChromaDB / SQLite / BM25 JSON），首次运行自动建表
```

### 2.2 项目既有三大约定（Agentic 层必须复用，不新造轮子）

1. **工厂注册**：每个 `XFactory` 持有 `_PROVIDERS: dict[str, type]` + `register_provider/create/list_providers`，`create()` 用 dict 查找（无 if/elif 链），provider 构造契约 `provider_class(settings=settings, **override_kwargs)`。`EvaluatorFactory` 是最先进范例（含 `_LAZY_PROVIDERS` 懒加载 + `NoneEvaluator` 降级）。
2. **工具注册**：`ProtocolHandler.register_tool(name, description, input_schema, handler)`，`_register_default_tools()`（[protocol_handler.py:192](src/mcp_server/protocol_handler.py)）是唯一挂载点；`ToolDefinition` 已是"名称/描述/JSON-Schema/处理器"结构。
3. **None 降级**：功能关闭时返回 no-op provider（`NoneReranker`/`NoneEvaluator`），调用方无需分支。**新的 Agent 层必须提供 `NoneAgent`**。

### 2.3 演进路线图

| 阶段 | 名称 | 范围 | 本次 |
|---|---|---|---|
| Phase 0 | 配置治理 | 密钥治理 + env 优先 + 模板 | ✅ 实施 |
| Phase 1 | 可复现地基 | 依赖锁定 + 一键引导 + 自检 | ✅ 实施 |
| Phase 2 | 生成式问答链路 | answer_generator + refusal/confidence/grounding | 路线图 |
| Phase 3 | 评测闭环 | golden 补齐 + 多指标 + 报告对比 | 路线图 |
| Phase 4 | 数据版本与更新 | 孤儿 GC + 版本跟踪 + 原子更新 | ✅ 实施 |
| Phase 5 | Prompt + 文档 + CI | prompt 版本化 + REPRODUCE.md + CI | ✅ 实施 |
| Phase 6 | Agentic RAG 能力层 | Agent 循环/工具/路由/记忆/反射 | 路线图（前瞻设计，见 §9） |

依赖关系：Phase 2–6 全部依赖 Phase 0 的配置地基（env 优先 + 可扩展 settings）与 Phase 1 的可复现环境。

---

## 3. Phase 0 — 数据与配置治理（本次实施）

### 3.1 目标

配置"**无密钥入库、环境变量优先、新环境可生成**"，并为 Phase 6 的 `agent:` 段预留结构。

### 3.2 交付物

| 文件 | 操作 | 内容 |
|---|---|---|
| `config/settings.yaml.example` | 新增 | 脱敏模板（§3.3），末尾含注释掉的 `agent:` 段 |
| `config/.env.example` | 新增 | 全部环境变量文档（§3.4） |
| `.gitignore` | 修改 | 追加 `config/settings.yaml`、`reports/`；**不要**忽略 `uv.lock` |
| `src/core/settings.py` | 修改 | 新增 `_ENV_OVERRIDES` + `_apply_env_overrides()`（§3.5） |
| `tests/unit/test_config_loading.py` | 修改 | 新增用例（§3.6） |
| git 操作 | 执行 | `git rm --cached config/settings.yaml`（停止跟踪、保留本地文件） |

### 3.3 `config/settings.yaml.example`（脱敏模板）

```yaml
# Modular RAG MCP Server - 配置模板
# 复制为 config/settings.yaml 后填写，或用下方环境变量覆盖（env 优先于 yaml）。
# 密钥请使用环境变量，勿写入文件。

# =============================================================================
# LLM Configuration
# =============================================================================
llm:
  provider: "qwen"        # openai | azure | ollama | deepseek | qwen（与代码注册一致，无 gemini）
  model: "qwen-turbo"
  deployment_name: ""
  azure_endpoint: ""
  api_version: ""
  api_key: ""             # 用环境变量 LLM_API_KEY 注入
  base_url: ""            # 用环境变量 LLM_BASE_URL 注入（Ollama/私有化网关）
  temperature: 0.0
  max_tokens: 4096

# =============================================================================
# Embedding Configuration
# =============================================================================
embedding:
  provider: "qwen"        # openai | azure | ollama | qwen
  model: "text-embedding-v3"
  dimensions: 1024
  azure_endpoint: ""
  deployment_name: ""
  api_version: ""
  api_key: ""             # 环境变量 EMBEDDING_API_KEY
  base_url: ""            # 环境变量 EMBEDDING_BASE_URL

# =============================================================================
# Vision LLM Configuration（图像理解/字幕）
# =============================================================================
vision_llm:
  enabled: true
  provider: "qwen"        # openai | azure | ollama | qwen
  model: "qwen-vl-max"
  azure_endpoint: ""
  deployment_name: ""
  api_version: ""
  api_key: ""             # 环境变量 VISION_API_KEY
  base_url: ""            # 环境变量 VISION_BASE_URL
  max_image_size: 2048

# =============================================================================
# Vector Store Configuration
# =============================================================================
vector_store:
  provider: "chroma"      # chroma | qdrant | pinecone（本地默认 chroma）
  persist_directory: "./data/db/chroma"
  collection_name: "knowledge_hub"

# =============================================================================
# Retrieval Configuration
# =============================================================================
retrieval:
  dense_top_k: 20
  sparse_top_k: 20
  fusion_top_k: 10
  rrf_k: 60

# =============================================================================
# Rerank Configuration
# =============================================================================
rerank:
  enabled: false          # true 时用 LLM/cross-encoder 重排
  provider: "none"        # none | llm | cross_encoder
  model: "none"
  top_k: 5

# =============================================================================
# Evaluation Configuration
# =============================================================================
evaluation:
  enabled: false
  provider: "custom"      # custom | ragas | composite
  metrics:
    - "hit_rate"
    - "mrr"
    - "faithfulness"

# =============================================================================
# Observability Configuration
# =============================================================================
observability:
  log_level: "INFO"
  trace_enabled: true
  trace_file: "./logs/traces.jsonl"
  structured_logging: true

# =============================================================================
# Ingestion Configuration
# =============================================================================
ingestion:
  chunk_size: 1000
  chunk_overlap: 200
  splitter: "recursive"
  batch_size: 10
  chunk_refiner:
    use_llm: true
  metadata_enricher:
    use_llm: true

# =============================================================================
# Agentic RAG（Phase 6 预留，默认关闭；启用后走 Agent 循环而非直通检索）
# 对应 src/core/settings.py 的 AgentSettings 可选块，完整 schema 见 §9.4。
# =============================================================================
# agent:
#   enabled: false            # false → NoneAgent，保持 query_knowledge_hub 直通
#   strategy: "react"         # react | plan_and_execute | self_ask
#   max_iterations: 5
#   router: { enabled: true, provider: "rule" }
#   memory: { enabled: false, backend: "none", window_size: 10 }
#   reflection: { enabled: true, max_retrieval_rounds: 2 }
#   tools:
#     - "query_knowledge_hub"
#     - "list_collections"
#     - "get_document_summary"
```

### 3.4 `config/.env.example`

```bash
# 复制为 .env 并填写（bootstrap 不自动加载 .env，需手动 export 或由启动脚本读取）
# 优先级：环境变量 > settings.yaml

# LLM（通义千问 / OpenAI / 私有化网关）
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://llm.example.com/compatible-mode/v1
LLM_MODEL=qwen-turbo

# Embedding
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_BASE_URL=https://llm.example.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v3

# Vision LLM（可选，图像理解）
VISION_API_KEY=sk-xxx
VISION_BASE_URL=https://llm.example.com/compatible-mode/v1
```

### 3.5 `src/core/settings.py` 修改设计

新增模块级白名单映射与合并函数，在 `load_settings` 中 `Settings.from_dict(data)` **之前**调用：

```python
_ENV_OVERRIDES: dict[str, str] = {
    "LLM_API_KEY": "llm.api_key",
    "LLM_BASE_URL": "llm.base_url",
    "LLM_MODEL": "llm.model",
    "EMBEDDING_API_KEY": "embedding.api_key",
    "EMBEDDING_BASE_URL": "embedding.base_url",
    "EMBEDDING_MODEL": "embedding.model",
    "VISION_API_KEY": "vision_llm.api_key",
    "VISION_BASE_URL": "vision_llm.base_url",
    # Phase 6 追加示例："AGENT_ENABLED": "agent.enabled",
}

def _set_nested(data: dict, dotted: str, value: str) -> None: ...
def _apply_env_overrides(data: dict, environ: Mapping[str, str]) -> dict: ...
```

**设计要点**：
- **显式白名单**：只映射安全相关/常用键，不无脑覆盖全部 YAML，避免改变既有语义。
- **映射表结构**：`env → 点分路径`，Phase 6 加 agent 键只需逐条加行。
- 值非空才覆盖；保持 `Settings` frozen dataclass 结构不变、向后兼容。
- 用单测锁定"env 优先于 yaml"行为。

### 3.6 测试用例（`tests/unit/test_config_loading.py` 追加）

| 用例 | 断言 |
|---|---|
| 加载 example 模板 | `load_settings('config/settings.yaml.example')` 成功；`s.llm.api_key is None` |
| env 优先于 yaml | 设 `LLM_API_KEY=sk-test` 后加载 example → `s.llm.api_key == "sk-test"` |
| base_url env 覆盖 | 设 `EMBEDDING_BASE_URL=http://x` → `s.embedding.base_url == "http://x"` |
| 未设置 env 不改变 | 无 env → api_key 保持 yaml 值（None） |
| 空白 env 忽略 | `LLM_API_KEY=""` → 不覆盖 |
| 结构向后兼容 | 现有全部既有用例仍通过 |

### 3.7 验证命令

```bash
python -c "from src.core.settings import load_settings; s=load_settings('config/settings.yaml.example'); print(s.llm.api_key)"   # None
LLM_API_KEY=sk-test python -c "from src.core.settings import load_settings; s=load_settings('config/settings.yaml.example'); assert s.llm.api_key=='sk-test'; print('env-overrides OK')"
python -m pytest tests/unit/test_config_loading.py -q
git check-ignore config/settings.yaml   # 期望命中
```

> ⚠️ **安全注意**：真实 key 已存在于 git 历史（`6dc4054`、`aa08e74`）。本次只做"停止跟踪 + gitignore + env 化"，**强烈建议尽快在阿里云百炼轮换该 key**；历史清理是独立事项，不在本次范围。

---

## 4. Phase 1 — 依赖锁定 + 一键引导 + 环境自检（本次实施）

### 4.1 目标

新环境 `git clone → 一条命令 → 可运行`；补上缺失的环境自检；锁定 Python 3.12。

### 4.2 交付物

| 文件 | 操作 | 内容 |
|---|---|---|
| `.python-version` | 新增 | `3.12`（用户已确认固定 3.12 为可复现目标） |
| `pyproject.toml` | 修改 | `requires-python = ">=3.12,<3.13"`；classifiers 更新为 3.12 |
| `uv.lock` | 生成 | `uv lock` 生成并**提交入库**（3.12 目标下解析） |
| `scripts/self_check.py` | 新增 | 环境自检（§4.3） |
| `scripts/bootstrap.py` | 新增 | 跨平台一键引导（§4.4） |
| `scripts/seed_docs.py` | 新增 | 幂等摄取 sample 文档（§4.5） |
| `bootstrap.bat` / `.ps1` / `.sh` | 新增 | 薄壳转发到 `python scripts/bootstrap.py` |
| `README.md` | 修改 | "快速开始"改为精确可复制命令 |

### 4.3 `scripts/self_check.py` 设计

签名：`run_self_check() -> int`（全过返回 0，任一 FAIL 返回 1）。

| 检查项 | 判定标准 | FAIL 影响 |
|---|---|---|
| 1. Python 版本 | `sys.version_info >= (3,12)` | 阻断 |
| 2. 配置可加载 | 依次尝试 `config/settings.yaml`、`config/settings.yaml.example` | 阻断 |
| 3. 关键包可 import | `mcp`、`chromadb`、`streamlit`、`yaml`、`markitdown`、`jieba` | 阻断 |
| 4. 数据目录可写 | `data/db/`（及 chroma/bm25 子目录）可创建 | 阻断 |
| 5. Chroma 可连接 | `PersistentClient` + `get_or_create_collection` 成功 | 阻断 |
| 6. SQLite 可建 | `data/db/ingestion_history.db` 可连接 + `CREATE TABLE IF NOT EXISTS` | 阻断 |
| 7. BM25 索引可写 | `data/db/bm25/` 可创建 JSON | 阻断 |
| 8. traces 可写 | `logs/traces.jsonl` 可追加 | 警告 |
| 9. （提示）密钥就绪 | 若 `settings.llm.api_key` 为空 → 提示用 `LLM_API_KEY` | 提示非阻断 |

输出：逐项 `[OK]`/`[FAIL]` + 汇总行；`--json` 输出 JSON 便于 CI；`--config <path>` 指定配置。

### 4.4 `scripts/bootstrap.py` 设计

流程（伪代码）：
```
1. 解析参数：--seed / --full / --venv <path>（默认 .venv，见 4.4.1）/ --verbose
2. 检查 uv：shutil.which("uv") 不存在 → 报错并给出安装指引
3. 确定 venv 路径（4.4.1）
4. uv venv <path> --python 3.12            # 不存在则创建
5. VIRTUAL_ENV=<path> uv sync --locked     # 严格按 uv.lock 安装（CWD=项目根）
6. 若 config/settings.yaml 不存在 → 复制 settings.yaml.example
7. 用 venv python 运行 scripts/self_check.py
8. --seed：运行 scripts/seed_docs.py
9. --full：运行 scripts/query.py -q "什么是混合检索"（示例查询，走检索链路无需 LLM）
10. 汇总 + 退出码
```

**4.4.1 venv 路径策略（不破坏现有环境）**：
- `.venv` 不存在 → 创建 `.venv`（Python 3.12）
- `.venv` 存在且版本 = 3.12 → 复用
- `.venv` 存在且版本 ≠ 3.12（如当前 3.14.6）→ 使用 `.venv-3.12`，**不动现有 3.14 环境**

### 4.5 `scripts/seed_docs.py` 设计

- 遍历 `tests/fixtures/sample_documents/`（PDF/txt，已存在）
- 摄取到 `default` collection：先查重（复用 `DocumentManager.list_documents` 按 source_path），已摄取跳过 → **幂等**
- 未摄取：`run_pipeline(file_path, collection="default")`（复用 [src/ingestion/pipeline.py](src/ingestion/pipeline.py) 的 `run_pipeline`）
- `--clean`：先用 `DocumentManager.delete_document` 清理再重摄
- 输出每文件结果汇总（摄取/跳过/失败）

### 4.6 设计说明

- **锁文件用 uv**：`uv` 已在 PATH；`uv lock` 直接消费 pyproject.toml；bootstrap 一律 `uv sync --locked` 保证严格一致。
- **Python 3.12**：wheel 覆盖最广、全新环境最稳；`.python-version` + `requires-python` 双保险。
- **一个 Python 逻辑 + 三壳转发**：避免维护多套脚本逻辑。
- 复用现有：`run_pipeline`、`DocumentManager`、`load_settings`、`data/` 自动建表机制。

### 4.7 验证命令

```bash
python scripts/self_check.py                    # 期望全绿（退出码 0）
python scripts/bootstrap.py --seed              # 建 3.12 venv + uv sync --locked + 生成 settings + 自检 + 摄取 sample
uv sync --locked                                # 幂等验证（无改动输出）
python scripts/seed_docs.py                     # 幂等（再跑应跳过已摄取）
python scripts/query.py -q "什么是混合检索"     # 验证种子数据可查
python -m pytest tests/unit tests/e2e/test_mcp_client.py -q -m "not llm"   # 回归不破坏
```

---

## 5. Phase 2 — 生成式问答链路（路线图，详细设计）

**目标**：补上"检索之后无生成"的最大算法缺口，且无 key 也能跑（extractive 模式）。

**交付**：`src/core/rag/answer_generator.py`

```python
@dataclass
class Answer:
    content: str
    citations: List[Citation]        # 复用 response_builder 的 Citation
    confidence: float                # 0-1，低置信可触发 refusal
    refusal_reason: Optional[str]    # 无检索结果/置信过低时填充

class BaseAnswerGenerator(ABC):
    def generate(self, query, chunks: List[RetrievalResult], trace=None) -> Answer: ...

class ExtractiveAnswerGenerator(BaseAnswerGenerator):
    # 无 key 离线可跑：从 top chunks 抽取要点 + 拼接 + 引用标记
class LLMAnswerGenerator(BaseAnswerGenerator):
    # 复用 LLMFactory.create(settings)；prompt 拼接 top chunks + 强制引用
class TemplateAnswerGenerator(BaseAnswerGenerator):
    # 固定模板，用于基线/测试
```

- `AnswerGeneratorFactory`：照抄工厂模板（`_PROVIDERS` + create + list_providers），默认 **extractive**（无 key 可跑）。
- **refusal/confidence/grounding 规则**：无检索结果 → refusal；置信低于阈值 → 明示"资料不足"；answer 引用必须落到返回的 chunk 上（grounding）。
- **接入**：`QueryKnowledgeHubTool.execute` 末尾调用；`MCPToolResponse` 增加 `answer`/`confidence`/`refusal_reason` 字段。
- 与 Phase 6 关系：`agent.enabled=true` 时走 Agent 循环（Agent 内部也可调用 answer_generator 收尾）。

---

## 6. Phase 3 — 评测闭环（路线图，详细设计）

**目标**：让评测指标真实可读，支持回归与对比。

**交付**：
- **补齐 golden**：为 [golden_test_set.json](tests/fixtures/golden_test_set.json) 填充 `expected_chunk_ids`/`expected_sources`——用 seed 文档的确定性 chunk_id（`{source_path_hash8}_{index:04d}_{content_hash8}`）标注，修复 hit_rate/mrr 恒 0。
- **修复 faithfulness**：`CustomEvaluator.SUPPORTED_METRICS` 当前只含 `{hit_rate, mrr}`，会静默丢弃 `faithfulness` → 扩展支持，或显式报错而非静默。
- **多指标**：`answer_correctness`（Ragas）、context_precision/relevancy。
- **报告**：`EvalReport.to_dict()` → 扩展输出 JSON 报告 + HTML 报告，支持两次评测对比（ablation：dense-only / sparse-only / hybrid / +rerank）。
- **复用**：`EvaluatorFactory` + `BaseEvaluator.evaluate(query, retrieved_chunks, generated_answer, ground_truth, trace)` + `EvalRunner` 编排；`evaluation.enabled=true` 时才启用。

---

## 7. Phase 4 — 数据版本与更新闭环（本次实施）

**目标**：数据更新不出孤儿、可回滚。

**交付**（实现见 `DEVELOPMENT_LOG.md` Phase 4 条目）：
- ✅ **修复 BM25 孤儿 bug**：新增 [src/ingestion/storage/chunk_ids.py](src/ingestion/storage/chunk_ids.py) `chunk_id_prefix()`，`remove_document`/`add_documents` 调用方统一改传**路径前缀**（原来是内容 hash 前缀，永远匹配不上存储的路径前缀 → 删除 no-op、重摄留孤儿）。
- ✅ **原子更新**：[document_manager.py](src/ingestion/document_manager.py) 跨 4 存储（Chroma/BM25/Image/SQLite）删除改为事务式（捕获快照 → 依次删除 → 失败用快照恢复 + 告警）；更新路径（同路径重摄）load 后识别 `is_update`，存储成功后清理旧版本残留。
- ✅ **文档版本跟踪**：[src/ingestion/versioning/version_store.py](src/ingestion/versioning/version_store.py) 新增 `document_versions` ledger + 内容快照（`data/versions/`）；支持按版本回滚某文档到上一内容版本（快照 + 重摄）。
- ✅ **孤儿 GC**：[src/ingestion/storage/orphan_gc.py](src/ingestion/storage/orphan_gc.py) 扫描 Chroma/BM25/Images/SQLite，删除不在 active 集（history success − ledger superseded）的残留；[scripts/gc.py](scripts/gc.py) 提供 `--collection` / `--dry-run` CLI。
- ⚠️ **rerank 保持关闭**（用户拍板）：Phase 3 ablation 的 `hybrid_rerank` 从未真正重排（`config_snapshot` 显示 rerank 禁用），无收益证据；等真实 rerank 评测（Phase 3 完善真实 rerank provider 后）再按下方约定默认开。

---

## 8. Phase 5 — Prompt 管理 + 文档 + CI（路线图，详细设计）

**交付**：
- **Prompt 版本化**：`prompts/` 目录存模板（markdown），带 `version`/`checksum`，settings 引用 prompt 名称；变更可回溯。
- **REPRODUCE.md**：把本设计的 Phase 0–1 流程固化为文档。
- **README 重写**：架构图 + 快速开始 + 配置说明。
- **GitHub Actions**：干净环境 `uv sync --locked` + `self_check` + `pytest -m "not llm"`，验证可复现。

---

## 9. Phase 6 — Agentic RAG 可扩展层（路线图，前瞻设计）

### 9.1 目标与原则

为 Agent 化能力（工具调用、路由、多跳检索、反射/自校正、记忆）预留干净缝隙，Phase 6 接入时**不改动现有核心**。设计完全复用 §2.2 三大约定。**`agent.enabled=false`（默认）时 NoneAgent 降级，保持现有直通检索零行为变化**——因此 Phase 0–1 不实现 Agent 能力也零风险。

### 9.2 已验证的扩展缝隙

| 缝隙 | 现状（读码确认） | Agent 层复用方式 |
|---|---|---|
| 工厂约定 | `EvaluatorFactory` 有 `_LAZY_PROVIDERS` + `NoneEvaluator` 降级（[evaluator_factory.py](src/libs/evaluator/evaluator_factory.py)） | `AgentFactory` 照抄模板；`enabled=false` → `NoneAgent` |
| 工具注册 | `ProtocolHandler.register_tool(...)` + `_register_default_tools()`（[protocol_handler.py:192](src/mcp_server/protocol_handler.py)）；`ToolDefinition` 已是工具描述结构 | 新 `agent_query` 工具在此挂载；`ToolDefinition` 天然是 Agent 工具描述 |
| LLM 缺口 | `BaseLLM.chat(messages)` 只支持 `Message(role, content)`，无 tool-call 结构（[base_llm.py](src/libs/llm/base_llm.py)） | `Message` 加可选 `tool_calls`/`tool_call_id`（向后兼容）；新增 `chat_with_tools()`，无工具后端降级为纯 chat |
| 检索编排 | `HybridSearch.search()` / `CoreReranker.rerank()` 均接受 `trace`、返回 `RetrievalResult` 列表（[hybrid_search.py](src/core/query_engine/hybrid_search.py)） | router/改写/反射即插即用；`ProcessedQuery.expanded_terms` 已声明未填充，是查询扩展现成槽位 |
| 可观测 | `TraceContext.record_stage()` 全链路透传；`trace_type` 为 `Literal["query","ingestion"]`（[trace_context.py](src/core/trace/trace_context.py)） | 扩为含 `"agent"`；Agent 各阶段（router/tool_call/reflection/answer）按 stage 记录 |
| 配置 | `Settings` 支持可选块（`ingestion`/`vision_llm` 先例）；`_ENV_OVERRIDES` 映射表逐条扩展 | 新增 `agent: Optional[AgentSettings]`，照抄 from_dict 可选块写法 |
| 评测复用 | `EvaluatorFactory` + `BaseEvaluator.evaluate(...)` + `EvalRunner`（[eval_runner.py](src/observability/evaluation/eval_runner.py)） | Agentic 评测替换 `_retrieve`/`_generate_answer` 内部为 Agent 循环；`QueryResult.generated_answer` 已就绪 |

### 9.3 目录结构（Phase 6 交付）

```
src/core/agent/
  __init__.py            # AgentFactory：register_provider/create/list_providers + NoneAgent 降级
  base_agent.py          # BaseAgent(ABC): run(query, trace) -> AgentResult
  agent_runner.py        # ReActAgent / PlanAndExecuteAgent / SelfAskAgent（工厂 providers，默认 react）
  base_tool.py           # BaseTool(ABC): name/description/input_schema + call()——包装 ToolDefinition
  tool_registry.py       # ToolRegistry：把 ProtocolHandler.tools 暴露为 Agent 可调用工具 + 外部工具白名单
  query_router.py        # QueryRouter：rule | llm 两 provider（rule 离线可跑，无需 key）
  query_understanding.py # 分解/改写/扩展：填充 ProcessedQuery.expanded_terms，供反射重检索
  memory.py              # ConversationMemory：none | sqlite 两后端，窗口式会话记忆
  reflection.py          # RetrievalReflector：检索质量反馈 → 改写/重检索（max_retrieval_rounds 上限）
src/mcp_server/tools/agent_query.py   # 新 MCP 工具：agent_query，register_tool 挂载进 _register_default_tools
```

### 9.4 `agent:` 配置 schema（对应 `AgentSettings` frozen dataclass）

```yaml
agent:
  enabled: false            # false → NoneAgent，保持 query_knowledge_hub 直通，零行为变化
  strategy: "react"         # react | plan_and_execute | self_ask
  max_iterations: 5
  router: { enabled: true, provider: "rule" }    # rule 离线可跑，llm 复用 LLMFactory
  memory: { enabled: false, backend: "none", window_size: 10 }   # sqlite 后端可选
  reflection: { enabled: true, max_retrieval_rounds: 2 }
  tools:                    # 白名单：agent 可调用的工具（后续可加 web_search/sql 等外部工具）
    - "query_knowledge_hub"
    - "list_collections"
    - "get_document_summary"
```

对应 `AgentSettings(max_iterations, strategy, router, memory, reflection, tools, ...)`；`_ENV_OVERRIDES` 可加 `AGENT_ENABLED→agent.enabled` 等键。

### 9.5 各模块设计要点

- **AgentFactory / BaseAgent**：`run(query, trace) -> AgentResult`；`AgentResult` 含 `answer`、`intermediate_steps`（工具调用轨迹）、`confidence`、`refusal_reason`。
- **ToolRegistry / BaseTool**：把现有 `ToolDefinition` 包装为 `BaseTool.call()`（校验 input_schema + 调用 `protocol_handler.execute_tool`）；白名单由 `agent.tools` 控制，**只暴露白名单内工具**（安全边界）。
- **QueryRouter**：`rule` 用关键词/正则路由（离线）；`llm` 用分类 prompt 路由（复用 LLMFactory）。路由目标：`direct_rag` / `multi_hop` / `tool`（如 web_search）。
- **Memory**：会话窗口记忆（short-term）；`sqlite` 后端做持久会话（复用 [file_integrity.py](src/libs/loader/file_integrity.py) 的 SQLite 模式）。
- **Reflection**：对检索结果做质量自评（覆盖率/置信），不足则改写 query（填充 `expanded_terms`）重检索，`max_retrieval_rounds` 兜底。
- **LLM tool-call 扩展**：`Message` 加可选字段；`chat_with_tools()` 抽象方法，`BaseLLM` 默认降级为把 tools 说明塞进 system prompt 的纯 chat（兼容无 function-calling 的 provider）。

### 9.6 双向 MCP 集成（企业级关键路径）

- **入站**：`agent_query` 工具注册进 `_register_default_tools`，MCP 客户端可直接调用 Agent。
- **出站**：`ToolRegistry` 复用 `protocol_handler.execute_tool(name, arguments)`，Agent 可调用现有检索/列表/摘要工具。
- **外部 MCP**：后续以 `McpToolSource` provider 形式接入外部 MCP server（web search / 公司内部数据库等），加入 `tools` 白名单——这是 RAG 接入企业内部工具的关键扩展点。

### 9.7 可复现性约束

Agent 层核心（rule router / NoneAgent / ReAct 纯 Python 编排）**零新增第三方依赖**；LLM 路由复用 `LLMFactory` 既有 provider，不引入锁文件变动，保持干净环境可复现。

---

## 10. 端到端交付验证（交付标准）

```bash
# 在全新临时目录模拟新环境
git clone <repo> /tmp/fresh && cd /tmp/fresh
bash bootstrap.sh --full            # 或 Windows: .\bootstrap.bat --full
# 期望：3.12 venv 就绪 → uv sync --locked 成功 → settings.yaml 从 example 生成（无 key）→ 自检全绿 → sample 摄取完成 → 示例查询返回结果

# Phase 0 专项
git check-ignore config/settings.yaml          # 命中
git ls-files config/settings.yaml              # 已停止跟踪
LLM_API_KEY=sk-test python scripts/query.py -q "test"   # 走 env 注入
```

完成后，任何新环境 clone 本项目 → 执行 `bootstrap` → 即得到可运行、有数据、可自检的 RAG 系统。

---

## 11. 风险与注意

| # | 风险 | 缓解 |
|---|---|---|
| 1 | pyproject 收紧到 `<3.13` 后，现有 3.14.6 的 `.venv` 不再满足 requires-python | 本次不重建它（bootstrap 用 `.venv-3.12`）；README 注明可复现目标 3.12 |
| 2 | env 覆盖改变既有语义 | 显式白名单 + 单测锁定行为 |
| 3 | 真实 key 仍在 git 历史 | 本次不删历史；用户尽快轮换 key；新 clone 不再带 key |
| 4 | seed 幂等被破坏（重复摄取产生孤儿） | chunk_id 确定性 + 摄取前查重 + `--clean` 强制重建 |
| 5 | uv.lock 与平台相关 wheel | 锁定 3.12 + 提交 uv.lock；CI 干净环境验证 |
| 6 | `agent:` 段过早启用导致行为变化 | 默认 `enabled: false` + NoneAgent 降级，Phase 0 只加注释模板不解析 |

## 12. 分阶段验收清单

- [ ] **Phase 0**：example 模板可加载无 key；env 覆盖生效；settings.yaml 已 gitignore + 停止跟踪；单测通过
- [ ] **Phase 1**：`.venv-3.12` 就绪；`uv sync --locked` 幂等；`self_check` 全绿；`bootstrap --seed` 一键可跑；seed 幂等
- [ ] **Phase 0–1 交付后**：全新 clone + `bootstrap --full` 通过（§10）
- [ ] **后续阶段**：Phase 2 生成、Phase 3 评测、Phase 4 数据版本、Phase 5 文档/CI、Phase 6 Agentic 能力层（均按 §5–§9 设计）
