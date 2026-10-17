# human-rlaif · v0.1.0

一个可安装的 AI 共学协作包。Agent 组织责任定位、人的参与约定、基线、真实任务、召回摩擦与复盘；人提供真实材料、参与关键判断，并带回现实反馈。

这是初始参考实现。自动化测试检查结构和文件操作；行为用例、真实宿主运行与长期学习效果分别验收。当前没有普遍能力提升承诺。

## 交给你的 agent

> 从 https://github.com/dlxeva/human-rlaif 安装 human-rlaif 技能。先阅读 SKILL.md 和安装说明，检查宿主能力，确认私人资料的保存位置；保留我的现有规范和文件。然后用我手头一个真实问题开始第一轮，共同确认 HUMAN.md 中对我的输入和参与要求。

安装来源：[dlxeva/human-rlaif](https://github.com/dlxeva/human-rlaif)。先将仓库获取到本地，再将仓库根目录的完整公共文件复制到宿主支持的技能目录，目录名为 `human-rlaif`。`SKILL.md` 位于仓库根目录。具体路径需由 agent 根据当前宿主核实。该目录自包含，可以独立分发。只有 SKILL.md 的单文件复制不完整。

本技能从 [pbl-loop](https://github.com/dlxeva/pbl-loop) 的 human-rlaif 实现迁出，作为独立仓库维护。pbl-loop 中的 `capability-loop` 无需同时安装；两者共享部分能力证据设计原则，human-rlaif 覆盖协作的参与标准和长期组织流程。来源、作者和迁移范围见 [迁移记录](PROVENANCE.md)。

## 日常使用

“这次按共学模式处理”“今天先赶交付”“复盘近期判断”“检查上次的待验证事项”“换一个新问题测一下”。支持 `production`、`learning`、`assessment`，可以随时暂停训练。

第一次只选一个领域和一项能力。让 agent 读取已有背景，再提供自己的真实问题与初步想法。粗糙口述可以使用，未知项需如实说明。首轮完成参与约定、初始样本和一次实际推进；完整基线在后续补足。

## 私人目录

在技能目录中、用户确认私人保存位置后运行，Python 3.10+，无第三方依赖：

```bash
python scripts/workspace.py init --workspace /absolute/private/path
python scripts/workspace.py doctor --workspace /absolute/private/path
python scripts/workspace.py record --workspace /absolute/private/path --event /absolute/path/episode.json
```

路径示例需要替换成获准位置。初始化拒绝 Git 工作树中的个人目录，重复运行会检查现状并保留已有内容。`init` 仅创建 draft 模板，agent 随后和本人确认协议。脚本不会安装宿主配置、创建提醒、改写个人原则或发送资料。

工作目录包含 HUMAN.md、BASELINE.md、STATE.md、JOURNAL.md、事件目录与格式标记。人审后的状态概要由 agent 在用户授权范围内维护，事件文件通过唯一 ID 保存。状态变更与验证结论不能从文件创建成功自动推导。

## 资料

- [核心 Skill](SKILL.md)
- [人的参与规范模板](assets/templates/HUMAN.md)
- [运行协议](references/protocol.md)
- [安装、恢复与升级](references/install.md)
- [虚构的完整案例](references/examples.md)
- [Human-RLAIF 论文与证据边界](references/research.md) · [SSRN 6928698](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6928698)

## 验证与许可

仓库根目录运行 `python -m unittest discover -s tests -p 'test_human_rlaif.py' -v` 和 `python scripts/validate_human_rlaif.py`。行为用例在 `evals/human-rlaif-cases.json`；运行方法在 `evals/HUMAN-RLAIF.md`。用例定义不等于模型实测通过。

技能代码和新文档沿用 [MIT 许可](LICENSE)。链接论文保留其自身许可；本包未复制论文全文、私人对话或未公开研究材料。
