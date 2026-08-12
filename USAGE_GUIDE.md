# 使用流程（USAGE GUIDE）

> 本文件是项目的**动手手册**：从全新 clone 配置环境，到启动 / 测试 / 日常使用 / 接入 AI 客户端，命令均可照抄执行。
> 想了解项目是什么，请看 [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)。
> 更详细的实测记录见 [ONBOARDING.md](ONBOARDING.md)。

---

## 0. 环境要求

| 项 | 要求 |
|---|---|
| 操作系统 | Windows / macOS / Linux（示例命令给出 Windows PowerShell 与 macOS/Linux 两种写法） |
| **uv** | **必须安装**（负责安装并管理 Python 3.12，系统无需预装 Python） |
| API Key | **可选**。检索-only 无需任何 key；完整功能（dense 检索、LLM 回答、图片理解）需要，见 §F |

安装 uv（没有时）：

```powershell
# Windows
winget install astral-sh.uv
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```

---

## A. 全新 clone 快速配置环境（5 步）

```powershell
# ① 克隆
git clone <repo-url> <你的目录>
cd <你的目录>

# ② 生成密钥文件（可选，检索-only 可跳过；.env 已被 gitignore）
copy config\.env.example config\.env    # macOS/Linux: cp config/.env.example config/.env
notepad config\.env                     # 按需填入 LLM / EMBEDDING / VISION 的 key

# ③ 一键引导（建 3.12 venv → uv sync --locked → 生成 settings.yaml → 自检 → 摄取示例 PDF）
.\bootstrap.bat --seed                  # macOS/Linux: ./bootstrap.sh --seed
# 不摄取示例文档就去掉 --seed；--full = --seed + 冒烟查询

# ④ 激活虚拟环境（后续命令直接可用 python）
.\.venv\Scripts\Activate.ps1            # macOS/Linux: source .venv/bin/activate

# ⑤ 自检 + 冒烟查询
python scripts\self_check.py            # 期望 [9/9 OK]，退出码 0
python scripts\query.py --query "什么是混合检索" --top-k 5
```

引导脚本 `scripts/bootstrap.py` 依次：检查 uv → 建 **Python 3.12** venv → `uv sync --locked`（严格按 `uv.lock` 装，含 dev 依赖，约 167 个包）→ 生成 `config/settings.yaml`（已存在则**不覆盖**）→ 跑环境自检 →（`--seed`）摄取示例 PDF。

**venv 路径规律**：全新目录建 `.venv`；若已存在非 3.12 的 `.venv`，则另建 `.venv-3.12` 且不碰原 `.venv`。手动等价步骤：

```bash
uv venv .venv --python 3.12
uv sync --locked --extra dev
python scripts/self_check.py
python scripts/prompts.py --verify
```

---

## B. 如何启动

项目是 **MCP Server（stdio）**，启动后默认监听标准输入输出，等 AI 客户端来握手。

| 目的 | 命令 | 说明 |
|---|---|---|
| 启动 MCP Server（供 AI 客户端调用） | `python main.py` 或 `mcp-server` | 两个入口启动**同一个** stdio 服务器；真入口在 `src/mcp_server/server.py`，`main.py` 是薄启动器（先校验配置，fail-fast） |
| 命令行查询 | `python scripts\query.py --query "..."` | 不依赖客户端，直接看检索结果 |
| 启动仪表盘 | `python scripts\start_dashboard.py --port 8501` | 浏览器打开 http://localhost:8501 |

> 说明：服务器自身**不摄取数据**——先运行 §D 的 `ingest.py` / `seed_docs.py` 把文档导入，再启动服务。

---

## C. 如何测试

pytest 已配置 markers：`unit / integration / e2e / llm / slow`，addopts `-v --tb=short`。

```bash
python -m pytest                          # 完整测试
python -m pytest -m "not llm"             # 排除真实 LLM API 测试（CI 同款，推荐先跑这个）
python -m pytest tests/unit/test_config_loading.py -q                # 单文件
python -m pytest tests/unit/test_config_loading.py::test_load_settings_success -q  # 单用例
python -m pytest -m "unit" -q             # 只跑单元测试（快）
```

Lint 与类型检查：

```bash
ruff check src tests
mypy src
```

---

## D. 日常使用流程

典型循环：**摄取 → 查询 → 评估 → 看仪表盘**，需要时做数据清理。

### 1) 摄取文档（PDF）

```bash
# 单个 PDF 或整个目录（递归，默认只认 .pdf）
python scripts\ingest.py --path <pdf文件或目录> --collection <集合名> [--force] [--dry-run]

# 摄取项目自带示例文档（幂等，重复执行自动跳过已入库）
python scripts\seed_docs.py [--collection default] [--clean]
```

> 注意：`ingestion.chunk_refiner.use_llm` / `metadata_enricher.use_llm` 默认 `true`，纯文本 PDF 也会调 LLM。想**纯离线摄取**，把 `config/settings.yaml` 里这两项改成 `false`。

### 2) 查询

```bash
python scripts\query.py --query "问题" [--collection <集合名>] [--top-k 10] [--no-rerank] [--no-answer] [--verbose]
```

输出为带 `[n]` 引用与 `source_path` 的结果列表；`--verbose` 打印 dense / sparse / 融合各阶段明细。检索链路：Dense → Sparse → RRF 融合 → 可选重排。

### 3) 评估

```bash
# 对 golden test set 批量评估，产出 reports/eval_*.json + .html
python scripts\evaluate.py [--test-set tests/fixtures/golden_test_set.json] [--collection <集合名>] [--top-k 10] [--json] [--ablate]

# 校验当前集合能否答到 golden set（source-level）；--refresh-ids 生成本机 chunk ids
python scripts\verify_golden_set.py [--collection <集合名>] [--refresh-ids]
```

### 4) 看仪表盘

```bash
python scripts\start_dashboard.py --port 8501
```

### 5) 数据维护

```bash
# 孤儿数据 GC（Phase 4：按内容哈希清理失活数据）；先 --dry-run 看会删什么
python scripts\gc.py --collection <集合名> --dry-run
```

### scripts 速查表

| 脚本 | 用途 | 常用参数 |
|---|---|---|
| `bootstrap.py` | 一键引导 | `--seed` / `--full` |
| `self_check.py` | 环境自检 9 项 | `--json` |
| `seed_docs.py` | 摄取示例 PDF（幂等） | `--collection` / `--clean` |
| `ingest.py` | 摄取 PDF / 目录 | `--path` / `--collection` / `--force` / `--dry-run` |
| `query.py` | 混合检索查询 | `--query` / `--collection` / `--top-k` / `--verbose` / `--no-answer` |
| `evaluate.py` | 评估报告 | `--test-set` / `--collection` / `--json` / `--ablate` |
| `verify_golden_set.py` | golden 命中校验 | `--collection` / `--refresh-ids` |
| `gc.py` | 孤儿数据清理 | `--collection` / `--dry-run` |
| `start_dashboard.py` | Streamlit 仪表盘 | `--port` |
| `prompts.py` | Prompt 模板 checksum 维护 | `--verify` / `--update-checksums` |

---

## E. MCP 客户端接入示例

> 本项目 MCP Server 走 **stdio**：客户端用 `python -m src.mcp_server.server`（或 `python main.py`）启动它，JSON-RPC 走 stdout、日志全在 stderr。以下配置均为参考模板，**路径按你的本机目录调整**。接入后重启客户端即可在对话中调用工具。

### E.1 接入后可用工具（4 个）

| 工具 | 功能 |
|---|---|
| `query_knowledge_hub` | 主检索：混合检索 + 融合 + 可选重排/回答，输出带 `[n]` 引用 Markdown；参数 `query`(必填) / `top_k`(1-20) / `collection` |
| `list_collections` | 列出所有集合及文档数 |
| `get_document_summary` | 按 `doc_id` 返回文档标题/摘要/标签/来源/块数 |
| `agent_query` | Agentic RAG（默认降级为与 `query_knowledge_hub` 等价的直通检索）；`session_id` 支持会话记忆 |

### E.2 Claude Code

项目根目录放 `.mcp.json`（**路径按本机替换**）：

```json
{
  "mcpServers": {
    "modular-rag": {
      "command": "F:/<你的克隆目录>/MODULAR-RAG-MCP-SERVER/.venv/Scripts/python.exe",
      "args": ["-m", "src.mcp_server.server"]
    }
  }
}
```

macOS/Linux 把 python 换成 `.venv/bin/python`；或用 `uv run`：

```json
{
  "mcpServers": {
    "modular-rag": {
      "command": "uv",
      "args": ["run", "--project", "/<你的克隆目录>/MODULAR-RAG-MCP-SERVER", "python", "-m", "src.mcp_server.server"]
    }
  }
}
```

等价命令行（需要 venv 已激活或给出完整 python 路径）：

```bash
claude mcp add modular-rag -- python -m src.mcp_server.server
claude mcp list   # 查看已注册的 MCP server
```

### E.3 Cursor

项目根目录创建 `.cursor/mcp.json`（结构同 E.2）：

```json
{
  "mcpServers": {
    "modular-rag": {
      "command": "F:/<你的克隆目录>/MODULAR-RAG-MCP-SERVER/.venv/Scripts/python.exe",
      "args": ["-m", "src.mcp_server.server"]
    }
  }
}
```

### E.4 GitHub Copilot

仓库级：在仓库根目录创建 `.github/copilot-mcp.json`；用户级：Windows 放 `%APPDATA%\GitHub Copilot\mcp.json`，macOS/Linux 放 `~/.config/github-copilot/mcp.json`。结构同 E.2。

> 提示：任何 stdio MCP 客户端，只要"启动命令 + 参数"指向本项目的 `python -m src.mcp_server.server`（cwd = 项目根目录）即可接入。

---

## F. 配置与密钥

### 配置优先级

```
进程环境变量  >  config/.env  >  config/settings.yaml
```

- 密钥与覆盖项放 `config/.env`（已 gitignore），**不要**写进 `settings.yaml`。
- `load_settings()` 启动时自动加载 `config/.env`（不存在则跳过）。

### .env 的 8 个变量（来自 config/.env.example）

```
LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
EMBEDDING_API_KEY / EMBEDDING_BASE_URL / EMBEDDING_MODEL
VISION_API_KEY / VISION_BASE_URL
```

### 切换后端

只改 `config/settings.yaml` 对应块的 `provider:` / `model:`：

- `llm.provider`: openai | azure | ollama | deepseek | qwen
- `embedding.provider`: openai | azure | ollama | qwen
- `rerank.enabled=false` + `provider: "none"`（默认关闭）
- `answer_generator.provider`: `extractive`（无需 key）| `llm`（复用 llm 配置）| `template` | `none`
- `agent.enabled: false`（默认检索-only；可用 `AGENT_ENABLED=true/false` 环境变量翻转）

### 无 key 也能跑的部分

- 检索：dense 失败**自动回退 sparse-only**（BM25/jieba）；
- 回答：extractive（从检索 chunk 抽取，不调 API）；
- 评估：custom（规则式，零 LLM 成本）；
- 完整离线：接**本地 Ollama**——`EMBEDDING_BASE_URL=http://localhost:11434/v1`、`EMBEDDING_API_KEY=ollama`、`embedding.provider=ollama`（LLM 同理）。

---

## G. 常见坑

1. **collection 命名不一致**：`scripts` 默认 collection 是 `default`，但 `config/settings.yaml` 里 `vector_store.collection_name` 默认 `knowledge_hub`。保持一致，别混传 `--collection`。
2. **离线摄取要关 LLM 后处理**：`config/settings.yaml` 的 `ingestion.chunk_refiner.use_llm` / `metadata_enricher.use_llm` 改为 `false`；含图 PDF 才需要 `VISION_API_KEY`。
3. **venv 路径两种**：`.venv`（全新目录）或 `.venv-3.12`（已存在非 3.12 的 `.venv` 时）。命令里按实际替换。
4. **启动 MCP Server 报配置错误**：`main.py` 会校验 `config/settings.yaml` 必须存在且合法（缺失退出码 1）。先跑一遍 `.\bootstrap.bat` 生成配置。
5. **`llm` 标记的测试**：`tests/integration/test_metadata_enricher_llm.py` 等真实调 API，需 key；日常跑 `pytest -m "not llm"`。
6. **修改 `prompts/*.md` 正文后**：运行 `python scripts/prompts.py --update-checksums` 回填 checksum，否则 `--verify`（CI 门禁）会失败。
7. **32 个已知单测失败不阻塞主链路**（详见 [ONBOARDING.md](ONBOARDING.md) §10：ragas 锁定依赖导入、embedding「无 key 应报错」断言、jieba 分词预期不一致等）。

---

## H. 深入阅读

| 文档 | 内容 |
|---|---|
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | 项目说明：是什么、架构、特性 |
| [README.md](README.md) | 完整介绍、使用策略、FAQ、简历参考 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 架构详解 |
| [DEV_SPEC.md](DEV_SPEC.md) | 开发规格文档（含测试策略 §4） |
| [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md) | Phase 0–6 改造记录 |
| [ONBOARDING.md](ONBOARDING.md) | 全新 clone 实测手册（含实测记录） |
| [REPRODUCE.md](REPRODUCE.md) | 环境可复现指南 |
