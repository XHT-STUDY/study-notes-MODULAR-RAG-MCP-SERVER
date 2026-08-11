# Modular RAG MCP Server — 全新 clone 跑通手册（实测版）

> 本文档按**在全新目录从零跑通**的完整流程编写，所有命令均在 Windows PowerShell 下实测通过（2026-08-10，Python 3.12.4 / uv / 通义千问 qwen provider；测试目录 `F:\xht_code\rag_test`）。

---

## 0. 前置准备

| 项 | 要求 | 说明 |
|---|---|---|
| 操作系统 | Windows（本手册命令为 PowerShell 风格） | macOS/Linux 用 `./bootstrap.sh`，venv 用 `.venv/bin/python` |
| uv | 必须安装 | 负责安装并管理 Python 3.12（系统 Python 是什么版本无所谓） |
| API Key | 检索必须 | 通义千问(DashScope) 或 OpenAI 兼容网关的 key（LLM / Embedding / Vision 各一） |

装 uv（没有时）：

```powershell
winget install astral-sh.uv
uv --version
```

---

## 1. 克隆项目

```powershell
git clone <repo-url> <你的克隆目录>
cd <你的克隆目录>
```

> 注意：clone 下来后，`config\settings.yaml` 和 `config\.env` **都不存在**（都被 gitignore），只有 `.example` 模板。必须自己生成。

---

## 2. 配置 API Key（引导前先做，检索需要）

```powershell
copy config\.env.example config\.env
notepad config\.env
```

按需填入这 8 个变量（`config\.env` 已被 gitignore，不会误提交）：

```
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://<网关>/compatible-mode/v1
LLM_MODEL=qwen-turbo
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_BASE_URL=https://<网关>/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v3
VISION_API_KEY=sk-xxx
VISION_BASE_URL=https://<网关>/compatible-mode/v1
```

---

## 3. 一键引导（建环境 + 自检）

```powershell
.\bootstrap.bat
# 等价于：python scripts\bootstrap.py
# 可加 --seed：自检后顺便摄取示例 PDF（需已配好 EMBEDDING key）
```

引导脚本 `scripts/bootstrap.py` 依次做：

1. 检查 `uv` 是否在 PATH；
2. 建 **Python 3.12** venv；
3. `uv sync --locked`（严格按 `uv.lock` 安装，含 dev 依赖，约 167 个包）；
4. `config\settings.yaml` 不存在时从 `settings.yaml.example` 生成（已存在则**不覆盖**）；
5. 用 venv 的 python 跑环境自检。

**venv 路径规律（重要）**：

- 全新目录 → 建 **`.venv`**（uv 自动找/装 3.12）
- 已存在但非 3.12 的 `.venv` → 另建 **`.venv-3.12`**，不碰原 `.venv`

后续命令里的 `\.venv\` 按实际情况换成 `.venv-3.12\`。也可以先激活环境，之后直接用 `python`：

```powershell
.\.venv\Scripts\Activate.ps1    # 激活后 python 即 venv 里的 3.12
```

**实测结果**：BOOTSTRAP COMPLETE，自检 9/9 OK、0 WARN、0 FAIL、Result: PASS。

---

## 4. 环境自检（可单独重跑）

```powershell
.\.venv\Scripts\python.exe scripts\self_check.py
# 期望 [9/9 OK]，退出码 0
```

9 项检查：Python 版本 / 配置可加载 / 关键包可 import / 数据目录可写 / Chroma 可连接 / SQLite 可建表 / BM25 可写 / 追踪日志可写 / API key 就绪。

---

## 5. 摄取示例文档（需要 EMBEDDING key）

```powershell
.\.venv\Scripts\python.exe scripts\seed_docs.py
# 幂等：重复执行会跳过已入库的文档（读取 ingestion_history.db）
```

等价手动摄取：

```powershell
.\.venv\Scripts\python.exe scripts\ingest.py --path tests\fixtures\sample_documents --collection default
```

**实测结果**：7 个示例 PDF 全量入库、0 失败，`default` collection 73 个 chunk。

---

## 6. 查询验证（混合检索链路）

```powershell
.\.venv\Scripts\python.exe scripts\query.py --query "什么是混合检索" --top-k 5 --verbose
```

链路：Dense（Chroma 向量）→ Sparse（BM25/jieba）→ RRF 融合 →（可选重排，默认关）。

**实测结果**：返回 Top5，每条带 `source_path` / `chunk_index` 引用，退出码 0。

---

## 7. MCP 服务器握手（真入口）

> `python main.py` 与 `mcp-server` 控制台命令均启动同一 stdio 服务器；真入口实现是 `src\mcp_server\server.py`（`main.py` 是薄启动器，先校验配置再委托）。

```powershell
$body = @'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"1.0"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
'@
$body | .\.venv\Scripts\python.exe -m src.mcp_server.server
```

**实测结果**：`initialize` 返回 `serverInfo=modular-rag-mcp-server v1.29.0` + capabilities；`tools/list` 返回 3 个工具：
`query_knowledge_hub` / `list_collections` / `get_document_summary`，退出码 0。

**给 AI 助手（Copilot / Claude Code / Cursor）配 MCP client 时**：

```
command: python
args: ["-m", "src.mcp_server.server"]
cwd: <你的克隆目录>
```

---

## 8.（可选）离线单测

```powershell
# 快速冒烟（22 个模块导入测试）
.\.venv\Scripts\python.exe -m pytest -m "unit" -q

# 完整离线单测
.\.venv\Scripts\python.exe -m pytest tests\unit -q -m "not llm"
```

**实测**：`-m "unit"` 22 通过；`tests\unit` 全量 1182 通过 / 32 失败 / 1 跳过（失败均为不阻塞项，见第 10 节）。

---

## 9.（可选）Streamlit 仪表盘

```powershell
.\.venv\Scripts\python.exe scripts\start_dashboard.py --port 8501
# 浏览器打开 http://localhost:8501
```

---

## 10. 注意事项 / 已知点

1. **venv 路径两种**：全新目录 `.venv`；已有非 3.12 `.venv` 时 `.venv-3.12`。命令里按实际替换。
2. **collection 命名**：`settings.yaml` 里 `vector_store.collection_name` 默认 `knowledge_hub`，但 `seed_docs.py` / `ingest.py` / `query.py` 默认 collection 是 `"default"`。保持默认一致即可，别混传 `--collection`。
3. **摄取会调 LLM**：`settings.yaml` 的 `ingestion.chunk_refiner.use_llm` 和 `metadata_enricher.use_llm` 默认 `true`，纯文本 PDF 也会调 LLM（需 `LLM_API_KEY`）；想纯离线摄取改成 `false`。含图 PDF 才需要 `VISION_API_KEY`。
4. **key 优先级**：进程环境变量 > `config\.env` > `settings.yaml`。密钥放 `config\.env`，别写进 `settings.yaml`。
5. **32 个单测失败不阻塞主链路**（三类）：
   - ragas 评估器 18 个：锁定依赖导入报错（`langchain_community.chat_models.vertexai` 缺失），`evaluation.enabled` 默认关；
   - embedding 提供方 5 个：本机已配置 key，导致「无 key 应报错」的断言不成立；
   - sparse_encoder / trace 等 9 个：jieba 分词与测试预期不一致等既有小 bug。

---

## 11. 本次实测记录（2026-08-10，测试目录 `F:\xht_code\rag_test`）

| 步骤 | 命令 | 结果 |
|---|---|---|
| 一键引导 | `python scripts\bootstrap.py` | venv `.venv`(3.12.4)，167 包，BOOTSTRAP COMPLETE |
| 环境自检 | `self_check.py` | 9/9 OK，Result: PASS |
| 摄取示例 | `seed_docs.py` | 7 PDF 入库，0 失败，73 chunks |
| 混合检索 | `query.py --query "什么是混合检索"` | Top5 带引用，exit 0 |
| MCP 握手 | `python -m src.mcp_server.server` | serverInfo v1.29.0 + 3 工具，exit 0 |
| 离线单测 | `pytest -m "unit"` | 22 passed |
| 完整单测 | `pytest tests\unit -m "not llm"` | 1182 passed / 32 failed / 1 skipped |

验证残留日志（可删）：`bootstrap_log.txt` / `seed_log.txt` / `query_log.txt`。
