# Modular RAG MCP Server

一个面向本地知识库的模块化 RAG 服务。它把 PDF 摄取、混合检索、答案生成、可观测性和 MCP 工具接口放在同一套工程中，可作为 MCP 客户端的知识检索后端，也可以通过命令行和仪表盘独立使用。

## 能做什么

- 摄取 PDF：解析文档、分块、补充元数据和图像描述，写入向量索引、BM25 索引及摄取记录。
- 混合检索：结合向量检索、BM25、RRF 融合和可选重排，返回带来源信息的结果。
- 回答生成：支持离线抽取式回答，也可接入 LLM 生成答案。
- MCP 服务：通过 stdio 暴露 `query_knowledge_hub`、`list_collections`、`get_document_summary` 和 `agent_query` 四个工具。
- 可观测与评估：记录摄取、查询和 Agent 追踪；提供仪表盘、黄金集评估与消融实验。

## 架构概览

```text
PDF 文档
  │
  ├─ 摄取：解析 → 分块 → 变换 → 向量化 → Chroma / BM25 / SQLite
  │
  └─ 查询：向量检索 + BM25 → RRF 融合 → 可选重排 → 回答与引用
                                      │
                         CLI / Streamlit / MCP stdio 工具
```

代码按职责分层：`src/ingestion` 负责摄取，`src/core` 负责检索、回答、追踪与 Agent，`src/libs` 提供可替换的模型和存储实现，`src/mcp_server` 与 `src/observability` 分别负责 MCP 接入和可视化。

## 快速开始

### 1. 准备环境

需要 Python 3.12 和 [uv](https://docs.astral.sh/uv/)。克隆仓库后执行：

```powershell
.\bootstrap.bat
```

macOS 或 Linux：

```bash
./bootstrap.sh
```

引导脚本会创建或复用 Python 3.12 虚拟环境，按 `uv.lock` 安装依赖，生成缺失的 `config/settings.yaml`，并运行环境自检。若现有 `.venv` 不是 Python 3.12，它会保留原环境并改用 `.venv-3.12`。

也可以手动执行：

```bash
uv venv .venv --python 3.12
uv sync --active --locked --extra dev
python scripts/self_check.py
```

### 2. 配置模型服务

`config/settings.yaml.example` 是完整配置模板。配置读取优先级为：进程环境变量 > `config/.env` > `config/settings.yaml`。

复制 `config/.env.example` 为 `config/.env`，至少填写摄取所需的 Embedding 配置：

```dotenv
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_BASE_URL=https://llm.example.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v3
```

默认模板使用通义千问，也可以在 `settings.yaml` 中切换到 OpenAI、Azure OpenAI、Ollama 或 DeepSeek 等已实现的提供方。请勿把真实密钥写入受 Git 追踪的文件。

没有 LLM 密钥时，仍可使用抽取式回答和已建好的索引。首次摄取文档需要可用的 Embedding 服务，或配置本地 Ollama Embedding。

### 3. 摄取文档

当前摄取入口只处理 PDF 文件，目录会递归扫描其中的 PDF：

```bash
uv run python scripts/ingest.py --path ./documents --collection handbook
```

常用选项：

```bash
# 只查看将要处理的文件
uv run python scripts/ingest.py --path ./documents --dry-run

# 忽略历史记录，强制重新摄取
uv run python scripts/ingest.py --path ./documents --collection handbook --force

# 摄取内置示例文档
uv run python scripts/seed_docs.py --collection demo
```

`bootstrap.bat --seed` 和 `./bootstrap.sh --seed` 会在完成环境初始化后自动摄取示例 PDF。`--full` 还会执行一次查询冒烟测试，因此两者都需要先配置 Embedding。

### 4. 查询知识库

```bash
uv run python scripts/query.py --query "如何配置混合检索？" --collection handbook --top-k 5
```

可加 `--verbose` 查看向量检索、BM25、融合和重排的中间结果；`--no-rerank` 关闭重排；`--no-answer` 只返回检索结果。

### 5. 启动仪表盘

```bash
uv run python scripts/start_dashboard.py --port 8501
```

默认访问地址为 `http://localhost:8501`。仪表盘包含数据浏览、摄取管理、摄取追踪、查询追踪和评估面板。

## 作为 MCP 服务使用

服务使用 stdio 传输，启动命令为：

```bash
uv run python main.py
```

将该命令配置到你的 MCP 客户端即可。以下是通用配置示例，按客户端要求替换项目绝对路径：

```json
{
  "mcpServers": {
    "modular-rag": {
      "command": "uv",
      "args": ["run", "python", "main.py"],
      "cwd": "F:/path/to/modular-rag-mcp-server"
    }
  }
}
```

启动前请确保 `config/settings.yaml` 存在且有效。MCP 协议占用标准输出，因此不要在同一终端把它当作交互式命令运行。

| 工具 | 用途 |
| --- | --- |
| `query_knowledge_hub` | 对指定集合执行混合检索并返回答案、引用和检索结果。 |
| `list_collections` | 列出可用文档集合及可选统计信息。 |
| `get_document_summary` | 按文档 ID 获取摘要、来源和元数据。 |
| `agent_query` | 执行 Agentic RAG 查询；未启用 Agent 时自动退化为普通混合检索。 |

在 `config/settings.yaml` 的 `agent.enabled` 设为 `true` 后，`agent_query` 才会运行 Agent 循环。默认关闭，便于在没有额外 LLM 配置时保持稳定的直通检索。

## 配置要点

`config/settings.yaml` 的主要配置块如下：

| 配置块 | 作用 |
| --- | --- |
| `llm` | 文本生成、LLM 重排和摄取阶段的 LLM 能力。 |
| `embedding` | 文档和查询的向量化，摄取必需。 |
| `vision_llm` | 为 PDF 中的图片生成描述，可按需关闭。 |
| `vector_store` | 本地 Chroma 持久化路径和默认集合名。 |
| `retrieval` | 稠密检索、稀疏检索、融合结果数量和 RRF 参数。 |
| `rerank` | 可选的 LLM 或 cross-encoder 重排。 |
| `answer_generator` | `extractive`、`llm`、`template` 或 `none`。 |
| `agent` | Agent 策略、工具白名单、记忆和反思配置。 |
| `observability` | 日志等级、追踪开关和追踪文件位置。 |

运行数据默认保存在 `data/`，追踪日志默认写入 `logs/traces.jsonl`。删除或迁移这些目录前，请先确认是否需要保留已摄取的索引和追踪记录。

## 评估与质量检查

```bash
# 运行默认黄金集评估，报告写入 reports/
uv run python scripts/evaluate.py

# 比较 dense、sparse、hybrid、hybrid + rerank
uv run python scripts/evaluate.py --ablate

# 环境与 Prompt 模板检查
uv run python scripts/self_check.py
uv run python scripts/prompts.py --verify

# 运行不需要真实 LLM 的测试
uv run python -m pytest -m "not llm"
```

CI 使用锁定依赖执行环境自检、Prompt 校验、Ruff 和非 LLM 测试。提交前建议至少运行上述检查。

## 项目文档

- [USAGE_GUIDE.md](USAGE_GUIDE.md)：更完整的日常操作和配置说明。
- [REPRODUCE.md](REPRODUCE.md)：可复现环境、CI 对齐和排障说明。
- [ARCHITECTURE.md](ARCHITECTURE.md)：详细架构设计。
- [DEV_SPEC.md](DEV_SPEC.md)：开发规格与设计约束。
- [ONBOARDING.md](ONBOARDING.md)：从零跑通项目的操作手册。

## 开发约定

- Python 版本固定为 3.12，依赖版本由 `uv.lock` 锁定。
- 测试位于 `tests/`，示例 PDF 位于 `tests/fixtures/sample_documents/`。
- 新增或修改 Prompt 后，使用 `python scripts/prompts.py --update-checksums` 更新校验和，再执行 `--verify`。
- 不要提交 `config/.env`、真实 API 密钥、本地索引、日志或生成的评估报告。

## 许可证

项目元数据声明采用 MIT 许可证。
