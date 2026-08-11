# REPRODUCE.md — 环境可复现指南

> **目标**：让任何人在一台全新机器上，用固定的命令复现与 CI 完全一致的可运行环境，
> 不依赖任何手抄的安装步骤。这是 Phase 1（依赖锁定）与 Phase 5（CI 对齐）的落地说明。
> 一步步带界面的走法见 [ONBOARDING.md](ONBOARDING.md)（实测跑通手册）。

---

## 0. 前置条件

| 项 | 要求 | 说明 |
|---|---|---|
| Python | 3.12（由 uv 自动安装，系统版本无所谓） | 见 `.python-version` |
| uv | ≥ 0.5（建议最新 0.11.x） | `winget install astral-sh.uv` 或官网脚本 |
| 网络 | 可访问 PyPI | 首次安装需拉取全部依赖 |

验证：

```bash
uv --version
```

---

## 1. 一键路径（推荐）

```bash
.\bootstrap.bat --seed     # Windows
./bootstrap.sh --seed      # macOS / Linux
```

内部等价于以下步骤（全部失败即中止，不静默）：

1. 检查 `uv` 存在（不存在 → 明确报错退出）。
2. 选择 venv 目录：已存在 `.venv` 且 Python 版本正确则复用，否则新建 `.venv-3.12`。
3. `uv venv --python 3.12` 创建 Python 3.12 虚拟环境。
4. `uv sync --active --locked --extra dev` —— **严格按 `uv.lock` 安装**（不会偷偷升级任何依赖）。
5. 若无 `config/settings.yaml`，从 `config/settings.yaml.example` 复制生成（默认 provider 为 qwen）。
6. `python scripts/self_check.py` —— 环境自检，**任一阻塞项失败立即中止**。
7. `--seed` 时：`python scripts/seed_docs.py` 摄取 `tests/fixtures/sample_documents/` 的示例 PDF。
8. `--full` 时：追加一条冒烟查询 `python scripts/query.py --query "什么是混合检索"`（需要 Embedding key）。

---

## 2. 手动等价步骤

以下命令与一键路径做的是同一件事，供不愿跑 bootstrap 或需要分步排障时使用：

```bash
uv venv .venv --python 3.12
uv sync --active --locked --extra dev

# 环境自检（9 项，无 API key 也全绿；1-7 阻塞，8 WARN / 9 HINT 非阻塞）
python scripts/self_check.py

# Prompt 模板校验（CI 同款门禁；checksum 不匹配时 exit 1）
python scripts/prompts.py --verify

# 摄取示例文档（幂等；需要 Embedding key 或本地 Ollama）
python scripts/seed_docs.py
```

> 已激活 venv 时命令前无需 `uv run`；未激活时把 `python` 换成 `uv run python` 即可。

---

## 3. 环境自检（self_check.py）语义

| # | 检查项 | 阻塞？ | 无 API key 时的表现 |
|---|---|---|---|
| 1 | Python 版本（3.12） | ✅ | — |
| 2 | 配置可加载（settings.yaml / example 回退） | ✅ | — |
| 3 | 关键依赖包可导入 | ✅ | — |
| 4 | data/ 目录可写 | ✅ | 运行时自建 |
| 5 | Chroma 可连接 | ✅ | — |
| 6 | SQLite 可创建 | ✅ | — |
| 7 | BM25 索引可写 | ✅ | — |
| 8 | 追踪日志可写 | ⚠️ WARN | — |
| 9 | API key 就绪 | 💡 HINT | `set ... to enable LLM/embedding` |

- `exit 0` ⇔ 没有**阻塞**项 FAIL；WARN / HINT 永远不算失败。
- `--json` 输出结构化结果，供 CI 解析。
- 无任何 API key 时 9 项也全绿（只是第 9 项提示 key 缺失），因此 CI 无需密钥。

---

## 4. 测试与静态检查

```bash
# 全量单元/集成测试（排除真实 LLM 调用）
python -m pytest -m "not llm"

# 本次 Phase 5 涉及的 ruff 范围（仓库基线 7294 个历史违规不在 CI 门禁内）
ruff check src/core/prompts.py scripts/prompts.py tests/unit/test_prompt_registry.py

# 类型检查（本地建议跑，非 CI 门禁）
.\.venv-3.12\Scripts\mypy.exe src     # Windows
```

---

## 5. 与 CI 的一致性

GitHub Actions（`.github/workflows/ci.yml`）在 ubuntu-latest 上执行的是同款命令：
`uv sync --locked` → `self_check --json` → `prompts.py --verify` → `ruff`（Phase 5 文件）→ `pytest -m "not llm"`。
本机跑通上述命令 ≈ CI 绿灯；两者共享同一份 `uv.lock`，依赖版本不可能漂移。

---

## 6. 常见问题

- **`.venv` 里的 Python 版本不对 / mypy 报错**：本机若已有 Python 3.14 的 `.venv`，
  请用 `.venv-3.12`（`.\bootstrap.bat` 会自动选择）；`uv sync` 读 `.python-version` 强制 3.12。
- **`uv sync --locked` 失败**：删除 `.venv`/`.venv-3.12` 后重跑；切勿改 `uv.lock`（除非更新依赖后 `uv lock` 重新生成）。
- **Embedding 不可用**：检查 `config/settings.yaml` 的 `embedding.provider` 与 base_url/api_key；本地可用 Ollama 的 `ollama` provider。
