# human-rlaif

> Human Reinforcement Learning from AI Feedback · 一套面向真实任务的人机长期共学协作实践包。

**独立开源项目** | [开始安装](#给-agent-的安装指令) · [人的参与规范](assets/templates/HUMAN.md) · [研究论文](paper/README.md) · [与 PBL 的关系](RELATED_PROJECTS.md) · [引用本项目](CITATION.cff)

`human-rlaif` 是一个可安装的 [Agent Skill](https://agentskills.io/specification)。它帮助 Agent 组织责任定位、人的高标准输入与参与、初始基线、召回与思维摩擦、现实反馈、延迟复测和协作复盘。用户负责真实信息、关键判断、行动与验证，AI 负责完整建模、挑战与协作管理。

它是 **v0.1.0 参考实现**：本地结构与文件助手可以测试；模型行为、跨宿主兼容性、人的长期能力增长仍需要独立验证。本项目不提供成长效果保证。

## 给 Agent 的安装指令

> 请从 `https://github.com/dlxeva/human-rlaif` 安装整个 Agent Skill `human-rlaif`。先阅读仓库根目录 `SKILL.md` 和 `references/install.md`，检查宿主的技能加载与私人文件能力。获得我确认后创建私人工作区，和我一起确认 HUMAN.md 中人类的输入与协作规范，然后选择一个真实问题，先保存我的原始判断，再完成第一轮实践。不要上传个人记录，也不要覆盖已有状态。

完整复制本仓库根目录到宿主认可的 Skills 路径，保证 `SKILL.md` 与 `references/`、`assets/`、`scripts/` 同级。GitHub 链接安装、路径检测和跨会话恢复以具体宿主实际能力为准。`SKILL.md` 是技能入口，仓库根目录即技能目录。

## 三种模式

- `production`：尽快完成现实交付，人主导目标、取舍和验收。
- `learning`：保留人的独立尝试，按需安排召回、反例、证据检查与迁移练习。
- `assessment`：锁定任务与帮助条件，分别记录独立表现和协作表现。

可以用自然语言说「启动 human-rlaif」「这次按共学模式处理」「今天直接赶交付」「复盘一下」「换一个新任务测一下」。普通问答和情绪支持不自动加入训练。

## HUMAN.md：人也要承担高标准输入

[HUMAN.md 模板](assets/templates/HUMAN.md)包含人的参与承诺：提供真实且有边界的上下文；暴露已有判断、未知项和证据身份；解释关键采纳或拒绝；参与有成本的取舍；带回现实行动与结果。初次确认后才成为个人的协作协议。允许口语、不确定和未成熟的想法，必要时由 Agent 协助整理。AI 也必须遵守其自身的分析、检索、纠错与权限边界。

## 私人工作区

公共技能源码和私人的 `HUMAN.md`、`BASELINE.md`、`STATE.md`、`JOURNAL.md`、事件记录相互隔离。**个人工作区必须放在 Git 工作树外**，本包默认没有遥测、同步或自动公开行为。

本地脚本可选，需 Python 3.10+：

```bash
python scripts/workspace.py init --workspace /absolute/private/path
python scripts/workspace.py doctor --workspace /absolute/private/path
python scripts/workspace.py record --workspace /absolute/private/path --event /absolute/path/episode.json
```

这些操作只验证文件结构并保存明确事件。初始化只生成 draft 参与协议，不代表用户已经确认，更不能据此断定学习效果。详见 [安装说明](references/install.md) 与 [运行协议](references/protocol.md)。

## 研究依据与相关项目

- [Human-RLAIF 论文、正式引用与证据边界](paper/README.md)：[SSRN 6928698](https://doi.org/10.2139/ssrn.6928698)。论文全文仍由原始发布平台提供，当前仓库不包含 PDF 副本。
- [与 `pbl-loop` 的关系](RELATED_PROJECTS.md)：有关联的能力训练研究与实践项目，依赖关系为零。
- [虚构示例](references/examples.md)：只演示协议，不代表实证结果。

## 测试与许可

```bash
python scripts/validate_human_rlaif.py
python -m unittest discover -s tests -p 'test_human_rlaif.py' -v
```

[行为测试协议](evals/HUMAN-RLAIF.md) 与 [行为用例](evals/human-rlaif-cases.json) 已提供，但真实宿主运行和长期学习实验尚未完成。

公共代码与原创文档使用 [MIT 许可证](LICENSE)。论文保留发布平台及原作者的版权安排，MIT **不**覆盖论文全文。个人记录默认只属于使用者。
