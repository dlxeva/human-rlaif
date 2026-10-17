# 维护者发布说明

## 统一英文简介

An Agent Skill for practicing judgment through AI feedback and real-world checks.

README.en.md、此处和仓库 About 应使用同一简介。推荐 topics：`agent-skills`、`human-ai-collaboration`、`human-rlaif`、`reflective-learning`、`ai-literacy`。Topics 与 About 是远端仓库设置，不会随本文件或 PR 自动更新。

## 发布前检查

1. 在干净检出中运行 `python scripts/validate_human_rlaif.py`、`python -m unittest discover -s tests -p 'test*.py' -v` 与 CI 固定版本的 `skills-ref validate skill/human-rlaif`。
2. 检查确切待发布提交的 CI；不能用旧提交绿灯代替。保留既有失败及冻结评测，新结论另建 run。
3. 安装包只包含 `skill/human-rlaif/`，检查全部相对链接和模板。不得包含私人 HUMAN、日志、客户资料或凭据。
4. 审阅 [待发布说明](RELEASE_NOTES.md)，确认版本、兼容性与已知限制。版本号、tag 和 release 仅在维护者明确批准后创建；本次改进不发布。
5. 新提交使用 GitHub 设置中显示的 verified noreply 地址；只配置当前仓库，不改全局 Git 身份、不重写旧历史。可检查 `git show --format=fuller --no-patch HEAD`；提交中不应包含本机用户/主机邮箱。

## 论文

论文 PDF 不进入技能安装包。本仓库不再分发论文；如需另行发布稿本，先取得该稿本权利人的明确许可，并单独标明版本及许可证，不能沿用软件 MIT。
