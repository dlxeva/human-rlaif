先写下你的判断，让 AI 提一个关键挑战，再用真实结果检查自己判断得准不准。

- 以前凭感觉下结论 → 现在先写判断、依据和发生概率
- 以前直接要 AI 答案 → 现在先保留自己的首稿
- 以前聊过就算了 → 现在只抓一个关键反例或取舍
- 以前只看交付成功 → 现在对照原预测和现实结果
- 以前觉得“懂了” → 现在约定日期，用新题再试一次

以上是流程差异，尚不是测得的学习增益。

# human-rlaif

[English](README.en.md) · [开始安装](#安装和开始) · [技能入口](skill/human-rlaif/SKILL.md) · [研究论文](paper/README.md)

An Agent Skill for practicing judgment through AI feedback and real-world checks.

**证据边界：** v0.1 系列参考实现，研究基础是单作者探索性自我个案研究，无效果保证。名称中的“Reinforcement Learning”是人的练习与反馈循环的比喻，不训练模型或更新模型参数。

**评测摘要：** 测了合成任务中的 Agent 首轮行为、只读恢复与文件助手。原始 16 案有 11 项响应通过、1 项失败、4 项因前提缺失未完成；云端另有 3 项响应和 1 项只读恢复通过，详见[评测记录](evals/runs/)。还缺强隔离宿主的完整安装与连续恢复，以及真人真实行动后至少 7 天的新题复测；后者目前待完成，见[本轮验收与真人记录模板](evals/runs/2026-10-17-requirements-v2/)，不能用合成例子补齐。

## 什么时候用

你有一个真实决策想练，比如选方案、判断证据、复盘失误，或想知道自己到底有没有学会。说“帮我练判断”“复盘一下”或“review my judgment”即可；赶交付时说“今天直接做”，会切回 `production`。三个模式为交付 `production`、练习 `learning`、评估 `assessment`。

## 安装和开始

可以把下面这段发给你的 Agent：

> 请从 https://github.com/dlxeva/human-rlaif 安装 skill/human-rlaif/ 这个技能目录。先阅读其中的 SKILL.md 和 references/install.md，确认宿主与目标绝对路径，不覆盖已有技能。先用我的真实问题完成三步：保存我的判断和结果概率，给一个关键挑战，约定新题复测日期。完成 2–3 个小循环后再起草完整 HUMAN.md 和基线表，由我确认。私人保存需另行确认，不上传我的记录。

只安装 `skill/human-rlaif/`，不复制论文、测试或整个仓库。第一次不用填长表；从第一轮起就要求真实材料、保留未知、反馈前首稿，以及人的现实行动责任。见[最小示范对话](skill/human-rlaif/references/examples.md)、[中英术语表](skill/human-rlaif/references/glossary.md)。

## 保存、到期检查与校准

私人工作区放在 Git 工作树和 iCloud/Dropbox 等同步目录之外。Python 3.9+ 可选（3.9.6 实测通过），从仓库根目录运行：

```bash
python skill/human-rlaif/scripts/workspace.py init --workspace /absolute/private/path
python skill/human-rlaif/scripts/workspace.py record --workspace /absolute/private/path --event /absolute/path/event.json
python skill/human-rlaif/scripts/workspace.py due --workspace /absolute/private/path
python skill/human-rlaif/scripts/workspace.py calibration --workspace /absolute/private/path
```

每轮开始由 Agent 检查到期项；脚本不会自行启动或通知。预测校准优先看事先概率与后来结果，报告样本数、命中率与 Brier 分数。完整用法、v1/v2 兼容和本地脱敏导出见[安装说明](skill/human-rlaif/references/install.md)与[运行协议](skill/human-rlaif/references/protocol.md)。

## 开发、引用与许可

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
skills-ref validate skill/human-rlaif
python scripts/validate_human_rlaif.py
python -m unittest discover -s tests -p 'test*.py' -v
```

[行为评测协议](evals/HUMAN-RLAIF.md) · [研究与引用](paper/README.md) · [关联项目 pbl-loop](RELATED_PROJECTS.md) · [软件引用](CITATION.cff)

公共代码与原创文档采用 [MIT](LICENSE)。论文按其发布版本的版权与许可处理；私人记录由使用者控制。
