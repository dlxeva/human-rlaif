# 来源与独立仓库迁移

作者与版权归属：dlxeva（Lingxiao Du）；原提交作者显示为 lingxiaodu。原 MIT 许可证及 Copyright (c) 2026 dlxeva 原样保留。

- 源仓库：[dlxeva/pbl-loop](https://github.com/dlxeva/pbl-loop)。
- 源分支：`feat/human-rlaif-v0.1`。
- 来源提交：[09a5b606a440336baba0d081f4ed7811f80d3717](https://github.com/dlxeva/pbl-loop/commit/09a5b606a440336baba0d081f4ed7811f80d3717)。
- 原 [PR #3](https://github.com/dlxeva/pbl-loop/pull/3) 于 2026-10-17 09:01:21 UTC 关闭，未合并。迁移不改变源仓库、分支或 PR。
- 独立仓库：[dlxeva/human-rlaif](https://github.com/dlxeva/human-rlaif)。

## 文件范围

源提交新增 20 个文件。本仓库迁移其中 19 个：14 个技能文件提升至根目录，5 个测试、评测与工作流文件保留原相对位置。源仓库专用的 `HUMAN-RLAIF.md` 导航页不迁移，入口整合到本仓库 README。另新增本迁移记录和 .gitignore，共 21 个公开文件。

仅调整独立仓库入口、安装说明、脚本测试路径和论文入口核实说明；workspace.py、核心 SKILL、模板、合成案例和行为用例内容不变。保留原有 GitHub Actions 工作流及固定 action 提交。

| 原路径 | 独立仓库路径 |
| --- | --- |
| `human-rlaif/CHANGELOG.md` | `CHANGELOG.md` |
| `human-rlaif/LICENSE` | `LICENSE` |
| `human-rlaif/README.md` | `README.md` |
| `human-rlaif/SKILL.md` | `SKILL.md` |
| `human-rlaif/assets/event.example.json` | `assets/event.example.json` |
| `human-rlaif/assets/templates/BASELINE.md` | `assets/templates/BASELINE.md` |
| `human-rlaif/assets/templates/HUMAN.md` | `assets/templates/HUMAN.md` |
| `human-rlaif/assets/templates/JOURNAL.md` | `assets/templates/JOURNAL.md` |
| `human-rlaif/assets/templates/STATE.md` | `assets/templates/STATE.md` |
| `human-rlaif/references/examples.md` | `references/examples.md` |
| `human-rlaif/references/install.md` | `references/install.md` |
| `human-rlaif/references/protocol.md` | `references/protocol.md` |
| `human-rlaif/references/research.md` | `references/research.md` |
| `human-rlaif/scripts/workspace.py` | `scripts/workspace.py` |
| `.github/workflows/human-rlaif.yml` | `.github/workflows/human-rlaif.yml` |
| `evals/HUMAN-RLAIF.md` | `evals/HUMAN-RLAIF.md` |
| `evals/human-rlaif-cases.json` | `evals/human-rlaif-cases.json` |
| `scripts/validate_human_rlaif.py` | `scripts/validate_human_rlaif.py` |
| `tests/test_human_rlaif.py` | `tests/test_human_rlaif.py` |

## 迁移验证（2026-10-17）

源版本与迁移版本均通过 18 项 Python 脚本测试和结构校验。迁移版本 16 个模型行为用例仍为 `not_run`；真实宿主安装、跨会话验收和长期效果未在此测试。公开文件已逐项阅读并检查敏感路径与常见凭据模式；未包含真实私人记录、凭据或论文全文。assets/templates 中的 HUMAN、BASELINE、STATE、JOURNAL 仅为空白公共模板。

SSRN 链接已与作者公开索引核对。SSRN 正文读取返回 403；可选 Zenodo DOI 未能核实，本次不新增该链接。论文保留自身许可。
