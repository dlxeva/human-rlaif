# 发布来源与迁移记录

作者与版权归属：dlxeva（Lingxiao Du）；原提交作者显示为 lingxiaodu。原 MIT 许可证及 Copyright (c) 2026 dlxeva 原样保留。

## 最终发布来源

本仓库优先采用用户原对话中已准备的独立发布包 `human-rlaif-standalone-v0.1.0.zip`（33,717 bytes，2026-10-17），共 26 个公共文件。ZIP 的 SHA-256：`64c3284e1822e5a3cba9e707b89b4c76f35b7bb737107198f4e1d8a7bad3fc87`。

独立包包含完整技能、空白模板、合成案例、脚本与评测、GitHub 工作流、独立仓库说明和论文引用元数据；无论文 PDF。发布时额外保留本来源记录，共 27 个公开文件。对 ZIP 的调整仅有：合并原已发布的根目录私人状态忽略规则；在 paper/README.md 中明确日期、下载链接和论文许可的核验边界。其他 24 个文件与 ZIP 字节一致。

## 开发历史

- 源仓库：[dlxeva/pbl-loop](https://github.com/dlxeva/pbl-loop)。
- 源分支：`feat/human-rlaif-v0.1`。
- 来源提交：[09a5b606a440336baba0d081f4ed7811f80d3717](https://github.com/dlxeva/pbl-loop/commit/09a5b606a440336baba0d081f4ed7811f80d3717)。
- 原 [PR #3](https://github.com/dlxeva/pbl-loop/pull/3) 于 2026-10-17 09:01:21 UTC 关闭，未合并；源仓库、分支和 PR 均未改动。
- 最初迁移该提交 20 个新增文件中的 19 个：14 个技能文件提升至根目录，5 个测试、评测与工作流文件保留原相对位置。原仓库专用 HUMAN-RLAIF.md 导航页未迁入。该初始发布随后由现成独立包补齐；使用普通追加提交，未重写历史。

## 验证与边界（2026-10-17）

源版本与独立发布包均通过 18 项 Python 脚本测试和结构校验。16 个模型行为用例仍为 `not_run`；真实宿主安装、跨会话验收和长期效果未在此测试。公开文件已逐项阅读并检查敏感路径与常见凭据模式；未包含真实私人记录、凭据或论文全文。assets/templates 中的 HUMAN、BASELINE、STATE、JOURNAL 仅为空白公共模板。

SSRN 入口已与作者公开索引核对；Crossref 核实论文标题、Lingxiao Du 作者、2026 年和 DOI 10.2139/ssrn.6928698。SSRN 正文读取返回 403，具体写作与上线日期及论文许可仍待独立核实；可选 Zenodo DOI 未能核实，本次不新增该链接。论文保留自身许可。
