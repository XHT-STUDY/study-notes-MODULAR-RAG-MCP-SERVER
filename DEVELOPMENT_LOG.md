# 开发日志（Development Log）

本文件按阶段（Phase）记录每次开发的完整产出：**开发了哪些内容 / 测试方法与预期效果 / 改动原因 / 重点难点 / 应学到什么 / 验证结果**。

> 📌 **追加约定**：每完成一个 Phase 的开发，Claude Code 都会在本文件**顶部**（`---` 分隔线下方、`## Phase 0` 之前）插入一条新记录，并使用下方「条目模板」的结构。请勿修改已写入的历史条目。

---

## 条目模板

```markdown
## Phase N — <阶段名>（YYYY-MM-DD）

### 1. 本次开发了哪些内容
（交付物清单 + 每项做了什么）

### 2. 测试方法与预期效果
（测试命令 + 预期输出；测试成功后的实际效果）

### 3. 本次改动的原因
（问题/痛点 → 后果 → 本次如何解决）

### 4. 重点难点
（最难的决策点、取舍、踩过的坑）

### 5. 你应该学到什么
（知识点 / 模式 / 方法）

### 6. 验证结果与遗留事项
（实际跑出来的结果数字；遗留问题、安全提醒、下一步）
```

---

## Phase 2 — 生成式问答链路（2026-08-10）

### 1. 本次开发了哪些内容

按 `gaizao_plan.md` §5 交付 Phase 2「生成式问答链路」，补上"检索之后无生成"的算法缺口，且无 key 也能跑（extractive 离线模式）。用户拍板：模块放 `src/libs/answer_generator/`（与既有 6 个可插拔库一致，而非方案 §5 的 `src/core/rag/`）；`answer_generator.enabled` 默认 true、provider 默认 `extractive`。

- **新增 `src/libs/answer_generator/` 包（6 文件）**：
  - `base_answer_generator.py`：`Answer` dataclass（content/citations/confidence/refusal_reason）+ `BaseAnswerGenerator` ABC + `NoneAnswerGenerator` 降级 + 三条通用规则助手（无结果 refusal / 低置信提示 / grounding 校验）+ `extract_citation_indices`/`sanitize_citation_markers`。
  - `extractive_answer_generator.py`：默认离线生成器——jieba 关键词（复用 `DEFAULT_STOPWORDS`）→ 关键句抽取 → `[n]` 引用要点列表；confidence = 检索 top score。
  - `llm_answer_generator.py`：懒创建 LLM（复用 `LLMFactory.create`）+ grounding prompt + 越界引用剔除 + 无 key/异常/无有效引用静默降级 extractive。
  - `template_answer_generator.py`：固定模板（基线/测试）。
  - `answer_generator_factory.py`：照抄 `EvaluatorFactory` 模板（`_PROVIDERS` + `_LAZY_PROVIDERS` 预留 + enabled=false/none → NoneAnswerGenerator）。
  - `__init__.py`：re-export + 包级注册 provider（镜像 `llm/__init__.py`）。
- **`src/core/settings.py`**：新增 `AnswerGeneratorSettings` frozen dataclass + `Settings.answer_generator` 可选块（`if "answer_generator" in data` 分支，缺失用默认值，向后兼容）。
- **两份 YAML**（`config/settings.yaml` + `.example`）：追加 `answer_generator:` 段（enabled/provider/model/temperature/max_tokens/confidence_threshold/max_chunks）。
- **`src/core/response/response_builder.py`**：`MCPToolResponse` 加 `answer/confidence/refusal_reason` 字段；`to_dict()`/`to_mcp_content()` 按 None 省略新键（无 answer 时 wire 输出逐字节不变）；JSON 块条件补 `or self.answer`。
- **`src/mcp_server/tools/query_knowledge_hub.py`**：`execute()` 检索后、build 前调 answer_generator（`asyncio.to_thread` 包裹 + `trace.record_stage("answer_generation")`）；`_attach_answer` 前置 `## 回答` 段落到 content；`__init__` 可注入 generator 便于测试。
- **`scripts/query.py`**：`--no-answer` flag + ANSWER 段落打印 + confidence/refusal 显示。
- **测试**：7 个新 unit 测试文件（47 用例）+ 更新 3 个既有测试（config_loading/smoke_imports/response_builder）。

### 2. 测试方法与预期效果

```powershell
.\.venv-3.12\Scripts\python.exe -m pytest tests/unit/test_answer_generator_*.py tests/unit/test_query_knowledge_hub_answer.py tests/unit/test_mcp_tool_response_answer.py -q
.\.venv-3.12\Scripts\python.exe -m pytest tests/unit -m "not llm" -q -p no:cacheprovider
.\.venv-3.12\Scripts\python.exe -m pytest tests/e2e/test_mcp_client.py -q
.\.venv-3.12\Scripts\python.exe -m ruff check src/libs/answer_generator/
.\.venv-3.12\Scripts\python.exe -m mypy --python-version 3.12 src/libs/answer_generator/
.\.venv-3.12\Scripts\python.exe scripts/self_check.py
.\.venv-3.12\Scripts\python.exe scripts/query.py --query "什么是混合检索" --top-k 3
```

**预期效果**：无 key 也能生成答案（extractive 离线）；query_knowledge_hub 返回带 `## 回答` + `[n]` 引用的 MCP 响应；disabled 时行为与 Phase 2 前逐字节一致；LLM 路径失败静默降级不污染主链路。

### 3. 本次改动的原因

| 问题 | 后果 | 解决 |
|---|---|---|
| 系统仅检索、不生成 LLM 答案（gaizao_plan 问题 #3） | 用户拿到的是资料片段而非回答 | Phase 2 加 AnswerGenerator 链路 |
| 无 key 无法演示生成 | 有使用门槛 | 默认 extractive 离线生成器 |
| `MCPToolResponse` 无 answer 字段 | 无法透传生成结果 | 加 Optional 字段 + None 省略序列化 |
| LLM 生成失败（无 key/网络/越界引用） | 崩主链路或输出不可信 | 懒创建 + 捕获降级 + grounding 校验 |

### 4. 重点难点

- **向后兼容（最大难点）**：`MCPToolResponse` 加字段必须"None 时序列化省略"，保证 disabled 时 wire 输出与 Phase 2 前逐字节一致；`to_mcp_content` 的 JSON 块条件 `if self.citations or self.metadata` 需补 `or self.answer`，否则有 answer 无 citations 时不序列化——探索阶段发现的隐性坑。
- **LLM 降级设计**：`LLMFactory.create` 在无 key 时 provider `__init__` 抛 ValueError（qwen_llm），必须在 `_get_llm` 懒创建时捕获并缓存失败，避免长驻进程每次查询重试失败。
- **grounding 校验**：LLM 输出 `[99]` 越界标记剔除、无有效引用降级 extractive，保证 answer 引用永远落在返回 chunk 上。
- **置信度策略统一**：extractive/llm 都用 `chunks[0].score`（检索 top score，已归一化 0-1），两条路径可比；低置信只加提示不整段拒绝。
- **模块位置决策**：用户拍板 `src/libs/answer_generator/`（非方案 §5 的 `src/core/rag/`），与既有 6 个可插拔库架构一致。
- **测试隔离**：mock LLM 注入（`llm=` 参数）+ monkeypatch `_perform_search`/`_ensure_initialized` + 禁用 `TraceCollector.collect` 落盘。

### 5. 你应该学到什么

- 工厂注册模式的又一实例：照抄 `EvaluatorFactory` 模板（`_PROVIDERS` + `_LAZY_PROVIDERS` + None 降级 + 双入参兼容）。
- **RAG 的 grounding 原则**：答案引用必须落到检索返回的 chunk，越界引用剔除或降级。
- **可选块配置扩展**：frozen dataclass 追加带默认值字段 + `from_dict` 里 `if "xxx" in data` 分支，向后兼容。
- **MCP 响应向后兼容**：新增字段 None 时省略，wire 输出逐字节不变。
- **fail-safe 降级**：LLM 生成器任何失败（无 key/网络/grounding 失败）静默降级离线 extractive，查询链路永不崩。

### 6. 验证结果与遗留事项

**实测数字**（`.venv-3.12`，CPython 3.12.4）：
- 新增 unit 测试：**47 passed**（7 文件全绿）。
- 全量 `pytest tests/unit -m "not llm"`：**1230 passed / 32 failed / 1 skipped**（Phase 2 前基线 1182/32/1；+48 = 47 新用例 + 1 新 smoke import；32 个失败与基线**完全相同**——ragas 18、sparse_encoder 2、trace 2 等既有类目，**零新增回归**）。
- MCP e2e `test_mcp_client.py`：**6/7 通过**；唯一失败 `test_multiple_tool_calls_same_session` 是 Phase 1 §4 已记录的既有 flaky（突发多调用超 60s 超时，环境相关）。
- ruff：`src/libs/answer_generator/` + 7 个新测试 **All checks passed**（`ruff --fix` 自动修复 55 处 UP006/UP007/未用导入）；4 个被改既有文件 0 新错误（既有错误为基线风格问题）。
- mypy：`src/libs/answer_generator/` **Success, no issues found (6 files)**；全量 `mypy src` 仍被既有 numpy 3.12 stub 问题阻断（非本次引入）。
- `self_check.py`：**9 OK / 0 WARN / 0 FAIL**，Result PASS。
- 冒烟 `query.py --query "什么是混合检索"`：返回 `## 回答` + 关键句要点（带 `[1]`/`[2]` 引用）+ `confidence=0.03` + `low_confidence` 提示（top score 低属预期行为）。
- MCP wire 核验：`to_mcp_content()` 2 个块（主文本 + 结构化 JSON），JSON 含 `answer`/`confidence`/`refusalReason` 字段。

**遗留事项**：
- 未 commit（待用户确认）。
- `test_multiple_tool_calls_same_session` e2e 超时为既有环境问题。
- `LLMAnswerGenerator` 的 llm provider 路径未用真实 key 端到端验证（本机 key 可能已失效）；逻辑已用 mock 覆盖。
- `answer_generator.enabled=true` 默认开启后，`query_knowledge_hub` 输出较之前多了 `## 回答` 段落——语义变化符合 Phase 2 目标；如需严格回归可 `enabled: false`。
- 真实 key 仍在 git 历史，需用户轮换（沿用 Phase 0 提醒）。

---

## Phase 0 优化 — 配置去重：.env 生效并接管密钥（2026-08-07）

### 1. 本次开发了哪些内容

让原本**不生效的死文档 `config/.env`** 真正参与配置加载，并把真实密钥从 `settings.yaml` 剥离：

- **`src/core/settings.py`**：接入 `python-dotenv` —— `load_settings()` 在解析 YAML 前自动加载 `config/.env`（文件不存在则跳过），`load_dotenv(override=False)` 保证「进程环境变量 > .env > yaml」。新增 `DEFAULT_ENV_FILE` 常量与 keyword-only `env_file=` 参数（现约 30 个调用点均不受影响）。
- **`src/core/settings.py`**：修复 `_apply_env_overrides` 潜在 bug —— env 覆盖只作用于 YAML **已存在**的顶层 section。此前 `VISION_API_KEY`/`VISION_BASE_URL` 会把缺失的 `vision_llm` 复活成 `vision_llm: {api_key: ...}` 残缺 dict，导致 `from_dict` 抛 `Missing required field: vision_llm.enabled` 崩溃（本次测试暴露的根因）。
- **`pyproject.toml` + `uv.lock`**：新增依赖 `python-dotenv>=1.0`，`uv lock` 重新生成锁文件。
- **`config/.env`（新建，gitignored）**：真实密钥/BaseURL 从 settings.yaml 迁入（8 个变量）。
- **`config/settings.yaml`**：`llm`/`embedding`/`vision_llm` 三段的 `api_key`/`base_url` 置空，`model`/`provider` 等保留。
- **`config/.env.example` / `config/settings.yaml.example`**：头部注释更新为「自动加载 + 优先级：进程环境变量 > config/.env > settings.yaml」。
- **`tests/unit/conftest.py`（新建）**：autouse `_isolate_dotenv` fixture，将 `DEFAULT_ENV_FILE` 指向不存在路径，保证单测不加载真实 .env；集成/端到端测试仍加载真实 .env 以连真实 API（保持迁移前「密钥在 yaml」时的行为）。
- **`tests/unit/test_config_loading.py`**：新增 3 个 dotenv 用例（dotenv 覆盖 YAML / 进程 env 优先 / 缺失 .env 无副作用）。
- **`CLAUDE.md`**：新增「配置约定」说明。

### 2. 测试方法与预期效果

```powershell
.\.venv-3.12\Scripts\python.exe -m pytest tests/unit/test_config_loading.py -q
.\.venv-3.12\Scripts\python.exe -m pytest -m "not llm" -q --tb=no -p no:cacheprovider   # 与基线 diff
.\.venv-3.12\Scripts\python.exe -m ruff check src/core/settings.py tests/conftest.py tests/unit/conftest.py tests/unit/test_config_loading.py
.\.venv-3.12\Scripts\python.exe -m mypy src/core/settings.py
.\.venv-3.12\Scripts\python.exe scripts/self_check.py
.\.venv-3.12\Scripts\python.exe scripts/query.py --query "模块化 RAG 架构" --top-k 3
```

**预期效果**：dotenv 用例通过；真实 .env 不再污染/破坏单测；`self_check` 9/9 通过；一次真实查询确认密钥经 `.env` 注入。

### 3. 本次改动的原因

| 问题 | 后果 | 解决 |
|---|---|---|
| 代码从不加载 `.env`（无 dotenv 依赖） | 用户按模板填 `.env` 不生效，纯死文档 | `load_settings` 自动加载 |
| `settings.yaml` 明文存真实密钥 | 与「密钥勿入文件」意图矛盾 | 密钥迁入 `.env`，yaml 留空 |
| 8 个 env 变量与 yaml 字段一一对应 | 同一信息两处存放，且 env 覆盖闲置 | 明确分工：`.env`=密钥/覆盖，yaml=其余配置 |

### 4. 重点难点

- **测试隔离（最大难点）**：`load_settings` 是全局唯一漏斗，一旦加载 `config/.env`，整个 pytest 进程的 `os.environ` 被真实密钥（含 `VISION_API_KEY` 等）污染。且 pytest 中 **module-scoped fixture 会在 function-scoped autouse fixture 之前实例化**，集成测试的 module 级 `settings` fixture 仍会加载真实 .env。最终双管齐下：①隔离 fixture 限定到 `tests/unit/`；②修复 `_apply_env_overrides`（env 不复活缺失 section），从根上杜绝崩溃。
- **Windows 环境**：`uv sync` 因 `.venv/Scripts` 目录被进程占用而失败，改用 `uv pip install --python <venv>` 装 dotenv。
- **ruff isort**：`from dotenv import load_dotenv` 应排在 `import yaml` 之后（straight-imports-first），用 `ruff --fix` 校准。

### 5. 你应该学到什么

- `python-dotenv` 的 `override=False` 语义与「进程 env > .env > 配置文件」优先级链。
- pytest fixture 作用域（function vs module）与 autouse 实例化顺序对全局副作用（`os.environ` 变异）隔离的影响。
- 在单一配置漏斗（`load_settings`）收敛加载逻辑，而非散落各入口。
- 秘密与配置分离的最佳实践：gitignored `.env` 管密钥，yaml 管非机密配置。

### 6. 验证结果与遗留事项

实际数字：

- `pytest tests/unit/test_config_loading.py`：**11 passed**（8 旧 + 3 新）。
- 全量 `pytest -m "not llm"`（与 `git stash` 基线 diff）：改动后 **76** 项 fail/error，基线 **80**。新增仅 `test_trace_context.py::test_total_elapsed_positive` —— 经基线隔离跑 5 次仍 fail 2 次，确认是既有 flaky 计时用例（`time.monotonic()` 返回 0.0），非本次引入；另有 5 个真实 API 摄取测试由 fail 转 pass（同为 flaky）。**零新增回归**。
- `ruff check`（4 个改动文件）：新增代码 **0 错误**；剩余 47 处为既有问题，与基线一致（仅行号偏移）。
- `mypy src/core/settings.py`：**Success, no issues**。
- `scripts/self_check.py`：**9 OK / 0 WARN / 0 FAIL**，Result PASS（[9/9] API keys ready 经 .env 注入）。
- `scripts/query.py --query "模块化 RAG 架构"`：返回 **3 条真实结果**（embedding API 调用成功，密钥经 .env 生效）。
- **遗留**：全量既有失败（ragas 版本 / jieba 分词 / azure 配置 / 计时 flaky）非本次引入；`config/.env` 含真实密钥（已 gitignored，勿提交）；git 历史仍留有旧 key，需用户轮换。

---

## Phase 1 修复 — mcp 版本锁定回归（2026-08-07）

### 1. 本次开发了哪些内容

修复全新 clone 后 **MCP 服务器启动即崩溃** 的锁文件回归：

- **`pyproject.toml`**：`mcp>=1.0.0` → `mcp>=1.28.1,<2.0.0`，并附注释说明原因（mcp 2.0.0 移除了 `lowlevel.Server.list_tools/call_tool` 装饰器，项目代码用的是 1.x 装饰器 API）。
- **`uv.lock`**：重新 `uv lock`，mcp `2.0.0 → 1.29.0`（PyPI 最新 1.x；2.0.0 是唯一 2.x）。顺带移除 mcp 2.x 专属依赖 `httpcore2`/`httpx2`/`mcp-types`/`truststore`。`uv.lock` 中 mcp 的唯一反向依赖就是项目自身，relock 干净无其他无关注入。
- **`tests/unit/test_protocol_handler.py`**：3 处 `create_mcp_server(...)` 传入预注册 handler 时补 `register_tools=False`。这是**既有测试 bug**（不是版本回归）：默认 `register_tools=True` 会把 `query_knowledge_hub` 等默认工具重复注册到已含同名工具的 handler，抛 `ValueError: Tool 'query_knowledge_hub' is already registered`。

### 2. 测试方法与预期效果

在 `.venv-3.12`（Phase 1 锁定目标环境，等价 fresh clone 的 `.venv`）下：

```powershell
.\.venv-3.12\Scripts\python.exe -m src.mcp_server.server     # 管道发 initialize，应握手成功而非崩溃
.\.venv-3.12\Scripts\python.exe -m pytest tests/e2e/test_mcp_client.py -q
.\.venv-3.12\Scripts\python.exe -m pytest tests/unit/test_protocol_handler.py tests/integration/test_mcp_server.py -q
.\.venv-3.12\Scripts\python.exe -m pytest -m "not llm" -q
```

**预期效果**：服务器能完成 `initialize → tools/list → tools/call` 全生命周期；此前全部 `Got: []` 的 e2e 转绿；全量失败数较 Phase 1 锁定基线（1162/56）明显下降。

### 3. 本次改动的原因

| 问题 | 后果 |
|---|---|
| `pyproject.toml` 声明 `mcp>=1.0.0`（无上界） | `uv lock` 解析到最新 **2.0.0** |
| mcp 2.0.0 移除 `lowlevel.Server.list_tools/call_tool` 装饰器 | `protocol_handler.py:246/252` 启动即抛 `AttributeError: 'Server' object has no attribute 'list_tools'` |
| e2e 服务器进程秒退 | `test_mcp_client.py` 全部 `Got: []`，MCP 核心能力在 fresh clone 上不可用 |

开发机 `.venv` 恰好是 mcp 1.28.1（未锁定），所以 Phase 1 阶段没暴露；全新 clone 用 `uv sync --locked` 严格按锁安装才复现。

### 4. 重点难点

- **方案取舍**：选「收紧上界锁回 1.x」而非「迁移到 mcp 2.0 `add_request_handler` API」——2.0 是预览版、迁移侵入大，且项目代码零 2.0 特性需求。
- **下界取值**：取 1.28.1（开发机实测兼容）而非 1.0.0，避免声明过宽。
- **判别「环境相关 vs 真回归」**：用隔离单测 + 系统 Python（mcp 1.28.1）复测那个失败的 protocol 用例，证明它是测试自身重复注册 bug 而非版本差异；再用 Phase 1 已记录的 `test_multiple_tool_calls_same_session` 突发 flake 对照，确认剩余的 1 个 e2e 失败是既有环境问题。

### 5. 你应该学到什么

- **无上界的 `>=` 依赖约束 + 锁文件 = 升级风暴隐患**：协议类关键依赖（mcp/ragas 等）应加 `,<major+1` 上界，否则 `uv lock` 一次 relock 就可能锁进破坏性大版本。
- **验证锁文件回归的黄金路径**：fresh clone + `bootstrap`（严格 `uv sync --locked`）是最真实的复现场景；开发机未锁定的 `.venv` 会掩盖这类问题。
- **测试自身 bug 的判别法**：把可疑用例放到已知兼容版本（系统 Python 1.28.1）单独跑，若照旧失败则非版本回归。

### 6. 验证结果与遗留事项

**实测数字**（`.venv-3.12`，CPython 3.12.4 + mcp 1.29.0）：
- 服务器启动：`initialize` 握手成功，返回 `serverInfo{name: modular-rag-mcp-server}`（修复前 AttributeError 秒崩）。
- e2e `test_mcp_client.py`：**7/7 通过**（修复前 7 个全 `Got: []`）。
- `test_protocol_handler.py` + `test_mcp_server.py`：**26/26 通过**（修复前 25/26，已修测试重复注册 bug）。
- 全量回归 `-m "not llm"`：**1300 passed / 47 failed / 8 skipped / 29 errors**（Phase 1 锁定基线 1162/56）。剩余失败全部为既有类目：ragas 17、azure provider 假设 11、Chroma 临时目录文件锁 20 error、embedding/reranker/refiner 缺 key、jieba、trace 结构等；唯一的 mcp 相关失败是 Phase 1 §4 已记录的 `test_multiple_tool_calls_same_session`（突发多调用超 60s，隔离运行 7/7 通过）。
- ruff：编辑的测试文件 23 处告警全部为**既有**（I001/UP035/UP006/F401/F841），本次改动 0 新增。

**遗留事项**：
- 未 commit / push（待用户确认后处理）。
- `DASHSCOPE_API_KEY` 环境变量已失效（阿里云 401），seed/冒烟查询需用户轮换后补跑。
- ragas 0.4.3 / jieba / Chroma 文件锁等既有失败按计划 Phase 3 处理。
- 已知 cosmetic 问题：`serverInfo.version` 显示的是 mcp SDK 版本（1.29.0）而非 `SERVER_VERSION`（0.1.0），`create_initialization_options` 未接项目版本常量，历史遗留，本次不处理。

---

## Phase 1 — 依赖锁定 + 一键引导 + 环境自检（2026-08-06）

### 1. 本次开发了哪些内容

按 `gaizao_plan.md` §4.2 交付清单，全部 8 项完成：

- **新增 `.python-version`（`3.12`）**：并移除 `.gitignore` 里的 `pyenv` 忽略块，使该文件可入库跟踪。
- **修改 `pyproject.toml`**：`requires-python = ">=3.12,<3.13"`；classifiers 收紧为 3.12（删除 3.10/3.11）。`ruff target-version`/`mypy python_version` 未动，避免引入新告警。
- **生成 `uv.lock`（328KB，171 个包）**：`uv lock` 在 CPython 3.12 下解析成功并提交入库；`.gitignore` 刻意不忽略它。
- **新增 `scripts/self_check.py`**：9 项环境自检（Python ≥3.12 / 配置可加载 / 关键包可 import / 数据目录可写 / Chroma 可连接 / SQLite 可建 / BM25 可写 / traces 可追加（警告）/ API key 就绪（提示））；`--json` 输出、`--config` 指定配置；任一阻断项 FAIL 返回退出码 1。
- **新增 `scripts/seed_docs.py`**：幂等摄取 `tests/fixtures/sample_documents/` 下的 PDF 到指定 collection；先查重（读 ingestion-history 表，与 `DocumentManager.list_documents` 同源）再摄取；`--clean` 用 `DocumentManager.delete_document` 清理后重摄；输出每文件 摄取/跳过/失败 汇总。
- **新增 `scripts/bootstrap.py`**（纯 stdlib，跨平台）：检查 `uv` → 按 §4.4.1 策略确定 venv 路径 → `uv venv <target> --python 3.12` → `uv sync --active --locked --extra dev`（严格锁 + dev 依赖）→ 缺 `config/settings.yaml` 时从 example 复制 → 用 venv python 跑 self_check → `--seed` 跑 seed_docs → `--full` 再跑 smoke query。
- **新增 `bootstrap.bat` / `.ps1` / `.sh`**：薄壳转发到 `python scripts/bootstrap.py`。
- **修改 `README.md`**：「快速开始」改为可复制的 bootstrap 命令 + 手动等价步骤 + API Key 环境变量说明。

### 2. 测试方法与预期效果

```powershell
# ① self_check（3.14 开发环境 + 3.12 目标环境）
python scripts/self_check.py                 # 9 OK，PASS，退出码 0
.\.venv-3.12\Scripts\python.exe scripts/self_check.py   # 同样 9 OK PASS

# ② 全量 bootstrap --seed（真实端到端）
python scripts/bootstrap.py --seed           # 退出码 0：建 3.12 venv → uv sync --locked（157 包）→ self_check 9 OK → 摄取 7 个 sample PDF

# ③ 幂等性
python scripts/seed_docs.py                  # 再跑：7 skipped / 0 failed，退出码 0
uv sync --locked                            # 再跑："Checked 157 packages in 78ms"，无改动

# ④ --full（含 smoke query）
python scripts/bootstrap.py --full           # 退出码 0；"什么是混合检索" 返回 5 条相关结果（chinese_*_doc.pdf）

# ⑤ Windows 壳
.\bootstrap.bat --seed / .\bootstrap.ps1 --seed   # 均 BOOTSTRAP COMPLETE，复用 .venv-3.12
```

**回归**：`pytest tests/unit tests/e2e/test_mcp_client.py -m "not llm"`（系统 Python 3.14）→ **1188 通过 / 30 失败**；与 HEAD 基线（`6dc4054`）对比，基线为 **1183 通过 / 29 失败**（+Phase 0 新增 6 个用例），30 个失败中有 29 个与基线**完全相同**，唯一多出的是 `test_multiple_tool_calls_same_session`（e2e，见 §4）。→ **本次改动未引入任何回归**。

### 3. 本次改动的原因

原 `pyproject.toml` 依赖全部 `>=`、无锁文件，全新环境 `pip install -e .` 无法复现；无 `.python-version`、无 bootstrap、无自检，新手 clone 后无从下手。Phase 1 目标：**一条命令从 clone 到可运行、有数据、可自检**，并把 Python 3.12 + `uv.lock` 定为可复现基线。

### 4. 重点难点

- **venv 路径策略**：现有 `.venv` 是 Python 3.14.6，不得破坏。bootstrap 读 `pyvenv.cfg` 判断版本——坑：uv 创建的 venv 写的是 `version_info = 3.12.4` 而非标准 `version = 3.12.4`，初版漏判导致把合法 3.12 venv 当成"不可读"重建（修复：两个 key 都检查）。重建用 `--clear` 而非 `--force`（uv 报错明确提示）。
- **`uv sync` 到自定义 venv**：默认 sync 到 `.venv`。用 `VIRTUAL_ENV=<path>` + `uv sync --active --locked` 定向到 `.venv-3.12`（已验证可行）。
- **dev 依赖不自动装**：`[project.optional-dependencies] dev` 不会随 `uv sync` 默认安装，导致 pytest 缺失。`--group dev` 报 "Group not defined"（那是 PEP 735 `[dependency-groups]` 专用）；正确写法是 `--extra dev`（保持 `pip install -e ".[dev]"` 兼容）。
- **Chroma collection 名校验**：`__self_check__` 非法（须以字母数字开头结尾），改用 `self_check_probe`。
- **`PdfLoader` 只收 `.pdf`**：seed_docs 因此只摄取 PDF，`sample.txt`/图片/`.py` 跳过并提示（不改 loader，保持"复用 run_pipeline"）。
- **e2e 冒烟依赖本机状态**：`test_multiple_tool_calls_same_session` 在有真实 `settings.yaml`+种子数据时，MCP server 处理"一次性突发多条真实工具调用"时未在 60s 内回齐响应（list_collections 单独发 0.4s 即回）；无 settings.yaml 的基线 worktree 里各 handler 秒失败，测试反而通过。→ 该测试结果是**环境相关**的既有 server 行为问题，非本次回归。

### 5. 你应该学到什么

- **uv 可复现工作流**：`.python-version`（决定默认解释器）→ `uv lock`（生成/校验锁）→ `uv sync --locked`（严格一致安装）→ `--extra dev`（装 optional 组）。`VIRTUAL_ENV` + `--active` 可把 sync 定向到任意 venv，不碰默认 `.venv`。
- **"一个 Python 逻辑 + 三壳转发"**：bootstrap 逻辑只在 `scripts/bootstrap.py`（stdlib-only，运行在被调用的任意 python 下），`.bat/.ps1/.sh` 只做转发，避免三套逻辑漂移。
- **幂等设计**：seed 先查重（读与 `DocumentManager` 同源的 ingestion-history 表）再摄取；chunk_id 确定性 + SHA-256 skip 双保险；`--clean` 走 `DocumentManager.delete_document` 跨 4 存储清理。
- **版本漂移的判别方法**：怀疑回归时用 `git worktree add HEAD` 建立基线目录，跑同一测试集 diff 失败集合——本次靠它证明 29/30 失败在基线已存在。
- **依赖锁与既有测试的张力**：`>=` 锁到最新会把 mcp 从 1.28.1 升到 2.0.0 等，e2e/单测对库版本敏感（Phase 3/5 再处理）。

### 6. 验证结果与遗留事项

**实测数字**：
- `self_check`：9 OK / PASS，退出码 0（3.14 与 3.12 环境一致）。
- `bootstrap --seed`：退出码 0；`.venv-3.12`（CPython 3.12.4）就绪；`uv sync --locked` 装 157 包；seed 摄取 **7 个 sample PDF / 73 chunks / 0 失败**。
- seed 幂等：再跑 **7 skipped / 0 failed**；`uv sync --locked` 再跑 78ms 无改动。
- `bootstrap --full`：退出码 0；smoke query 返回 **5 条**相关结果。
- 回归：系统 Python 3.14 → **1188 通过 / 30 失败**（基线 1183/29，唯一新增为环境相关 e2e，见 §4）；`.venv-3.12` 锁定环境 → 1162 通过 / 56 失败（多出的 26 个为 mcp 2.0.0 下 e2e/协议差异）。
- ruff：新脚本 **0 错误**；`ruff check src tests` 7332 个**既有**错误（主体是 CRLF 换行触发的 W293 blank-line-with-whitespace，共 5476，Windows checkout 全仓库现象），与本次改动无关。

**遗留事项**：
- 30 个测试失败（ragas 0.4.3 / jieba 分词 / trace 结构 / embedding smoke 环境变量 / mcp e2e 突发）为**既有库版本漂移**，建议 Phase 3 评测闭环时一并修。
- `mypy src` 在本机失败：mypy 2.3.0 + `python_version=3.10` 解析不了 numpy 的 3.12 `type` 语句 stub——既有环境问题，非本次引入。
- `sample.txt` 因 `PdfLoader` 只支持 PDF 未被 seed（有意为之，不改 loader）。
- `bootstrap.sh` 仅按 POSIX 惯例编写，本次未在 Linux/macOS 实测（本机 Windows）。
- 建议用户尽快轮换 git 历史中的真实 API key（沿用 Phase 0 提醒）。

---

## Phase 0 — 数据与配置治理（2026-08-06）

### 1. 本次开发了哪些内容

按 `gaizao_plan.md` §3.2 交付清单，全部 6 项完成：

- **新增 `config/settings.yaml.example`（脱敏模板）**：把 `config/settings.yaml` 里的真实 `sk-ws-...` 密钥全部替换为空字符串，并注释标明每个密钥该用哪个环境变量注入（`LLM_API_KEY` / `EMBEDDING_API_KEY` / `VISION_API_KEY` 等）；末尾包含**注释掉的** `agent:` 段（Phase 6 Agentic RAG 预留结构，本次不解析）；provider 注释与代码注册一致（无 gemini）。
- **新增 `config/.env.example`（环境变量文档）**：列出 LLM / Embedding / Vision 三组环境变量（key、base_url、model），声明优先级：**环境变量 > settings.yaml**。
- **修改 `.gitignore`**：追加 `config/settings.yaml` 和 `reports/`；**故意不忽略 `uv.lock`**（Phase 1 要提交锁文件）；两个模板文件不被忽略、可正常入库。
- **修改 `src/core/settings.py`（核心逻辑）**：新增 `_ENV_OVERRIDES` 白名单映射表（8 条 env → 点分路径）、`_set_nested()`（按点分路径写嵌套 dict）、`_apply_env_overrides()`（仅非空白值覆盖，env 优先于 yaml）、`_optional()`（`""` 归一化为 `None`）；调用时序变为 `yaml.safe_load` → `_apply_env_overrides` → `Settings.from_dict`。
- **修改 `tests/unit/test_config_loading.py`**：新增 `clean_env` fixture（遍历白名单清空环境变量防泄漏）+ 6 个用例（模板无密钥 / LLM_API_KEY env 优先 / EMBEDDING_BASE_URL 覆盖 / 无 env 保持 yaml 值 / 空白 env 忽略 / LLM_MODEL 覆盖）。
- **git 操作**：`git rm --cached config/settings.yaml` —— 停止跟踪、保留本地文件（本机开发仍可用真实 key）。

附带验证修复：mypy 报出 `_optional()` 返回 `Any`（项目开启 `warn_return_any`），已重写为类型安全实现；`mypy src/core/settings.py` 通过。

### 2. 测试方法与预期效果

> 注意：项目 `.venv` 当时**未安装 pytest**（Phase 1 环境治理要解决）；验证时用系统 Python（`PYTHONPATH=. python -m pytest ...`）。

```powershell
# ① 单元测试（预期：8 个用例全绿）
PYTHONPATH=. python -m pytest tests/unit/test_config_loading.py -q

# ② 模板加载无密钥（预期打印 None）
python -c "from src.core.settings import load_settings; s=load_settings('config/settings.yaml.example'); print(s.llm.api_key)"

# ③ 环境变量优先（预期打印 env-overrides OK）
$env:LLM_API_KEY="sk-test"; python -c "from src.core.settings import load_settings; s=load_settings('config/settings.yaml.example'); assert s.llm.api_key=='sk-test'; print('env-overrides OK')"

# ④ git 忽略生效（预期命中路径）
git check-ignore config/settings.yaml

# ⑤ 已停止跟踪（预期无输出）
git ls-files config/settings.yaml

# ⑥ 全量回归（预期不引入新失败）
PYTHONPATH=. python -m pytest tests/unit -q -m "not llm"
```

**预期效果**：模板可加载但无任何密钥（None）；设置环境变量后无需改 yaml 即可覆盖密钥/地址/模型；`config/settings.yaml` 已从 git 索引移除且被忽略；新环境 clone 后复制 `settings.yaml.example` 填环境变量即可运行，仓库中找不到真实密钥。

### 3. 本次改动的原因

| 问题 | 后果 |
|---|---|
| 真实 API Key 明文入库且被 git 跟踪 | 任何人 clone 仓库即泄露密钥（已存在于 git 历史 `6dc4054`、`aa08e74`） |
| 无环境变量优先机制 | 密钥无法从仓库外注入，改配置必须动文件 |
| 无脱敏模板 | 新环境 clone 后不知道该填哪些字段、密钥放哪 |
| 无 `.env.example` 文档 | 环境变量约定不存在，Phase 6 Agentic 层（需 `AGENT_ENABLED` 等）无从扩展 |

Phase 0 解决「密钥从源头不再入库 + env 优先 + 新环境可生成配置」，为 Phase 1（可复现）、Phase 6（agent 配置段）打地基。

### 4. 重点难点

1. **方案内部不一致的处置（最难决策点）**：方案 §3.3 模板写 `api_key: ""`，但 §3.6 测试断言 `s.llm.api_key is None`——两者冲突。通过新增 `_optional()` 归一化（`""`→`None`）同时满足两者，并给后续阶段统一契约（`None` = 未配置）。`""` 与 `None` 在全部下游 provider 中行为等价（已逐一核实 `or`/`if not` 消费方式），改动零风险、向后兼容。
2. **「只覆盖非空白值」的取舍**：env 变量为空字符串时**不能**覆盖 yaml 值，否则用户没配 env 会意外清空已有配置；白名单机制保证只有列出的 8 个键受 env 影响。
3. **mypy 严格模式**：项目开了 `warn_return_any`，`_optional()` 从 dict `.get()` 拿到 `Any` 直接返回会报错，必须显式收敛为 `str | None`。
4. **测试的隔离性**：宿主机的 `LLM_API_KEY` 等环境变量可能泄漏进测试导致 flaky，必须用 `clean_env` fixture 先清空白名单内所有变量。
5. **`git rm --cached` 语义**：只移出索引、保留工作区文件——本机开发不受影响，但后续 commit 会记录删除。

### 5. 你应该学到什么

- **12-factor 配置治理模式**：密钥类配置走环境变量、文件只存非敏感默认值。
- **白名单 env 覆盖 vs 全量覆盖**：只映射安全相关/常用键，避免改动既有语义——「克制」的设计。
- **向后兼容的验证方法**：改动配置解析时，检查所有下游消费方对 `""` 和 `None` 的等价性；用 `git stash` 回退对比测试确认失败是否既有。
- **mypy `warn_return_any` 的意义**：从 `dict.get()` 拿到的 `Any` 必须收敛到具体类型。
- **设计文档内部的矛盾要主动发现并解决**：不是照抄方案，而是让它自洽。

### 6. 验证结果与遗留事项

- 单测：`test_config_loading.py` **8/8 通过**（2 既有 + 6 新增）。
- mypy：`src/core/settings.py` 无错误。
- 全量回归：**1182 passed / 29 failed / 1 skipped**；这 29 个失败**全部是环境相关、与本次改动无关的既有失败**（用 `git stash` 回退后复测照旧：jieba 分词行为、Mock 真值判断、ragas/langchain 兼容、PDF 解析等，源于系统 Python 3.14 + 全局依赖版本）——**本次改动引入 0 个新失败**。
- 遗留：真实 key 仍存在于 **git 历史**中，本次只做到「停止入库 + gitignore + env 化」，**强烈建议尽快在阿里云百炼轮换该 key**；历史清理是独立事项。
- 未自动 commit，待用户 review 确认。
