# 发布为独立 GitHub 仓库

目标公开仓库：`dlxeva/human-rlaif`。请创建一个 **Public / Empty** 仓库，创建时不自动生成 README、.gitignore 和 LICENSE（本包已提供）。

- 仓库地址： https://github.com/new?name=human-rlaif
- 建议简介：`Human-RLAIF: an agent skill for reflective human–AI collaboration, rigorous human input, feedback and learning evidence.`
- 推荐 Topics：`agent-skills`, `human-ai-collaboration`, `human-rlaif`, `reflective-learning`, `ai-literacy`

创建后，可让有 GitHub 写入权限的 Agent 完成提交，也可以在本目录运行：

```bash
git init -b main
git add .
git commit -m "Initial standalone human-rlaif skill v0.1.0"
git remote add origin https://github.com/dlxeva/human-rlaif.git
git push -u origin main
```

命令需要 Git 用户信息及 GitHub 身份验证，执行前检查当前仓库是新建的 `human-rlaif` 而非别的项目。当前只包含公共 Skill、模板、测试、论文引用元数据和文档。不要把自己真正的 HUMAN.md、BASELINE.md、JOURNAL.md 或私人对话提交到远端。

独立仓库上线后，可在 `pbl-loop` 的 README 添加一个**纯文档链接**到 `human-rlaif`，说明两者关联且无需互相安装。不要把 `human-rlaif` 技能文件复制回 pbl-loop。

## 论文全文处理

当前 `paper/` 包含正式论文的引用、DOI 和发布版链接，**没有 PDF 再发布副本**。正式发布稿与许可状态核实后，可以选择额外保存确定版本的 PDF 于 `paper/releases/`，单独写清版本号和论文许可；MIT 仅适用于 Skill 代码与原创文档。
