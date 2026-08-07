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
