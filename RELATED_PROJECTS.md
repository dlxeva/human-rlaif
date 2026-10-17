# 项目关系：human-rlaif 与 pbl-loop

| 项目 | 代码仓库 | 核心关注 |
|---|---|---|
| human-rlaif | [dlxeva/human-rlaif](https://github.com/dlxeva/human-rlaif) | 长期人机共学：人的高标准参与协议、反馈循环、角色责任、基线、召回与摩擦、现实验证 |
| pbl-loop | [dlxeva/pbl-loop](https://github.com/dlxeva/pbl-loop) | 问题驱动的能力训练工作流与证据追踪（以该项目自身 README 为准） |

两者可以借鉴训练任务设计、能力基线、评估与证据追溯的方法。**当前没有跨仓库运行依赖。** `human-rlaif` 的 README 与 Skill 引用 PBL 仅供了解关联，不要求安装 pbl-loop，也不会修改 pbl-loop 的现有能力协议。

本仓库不把 pbl-loop 中的全部机制视为 Human-RLAIF 的组成，也不声明两者已经完成系统性理论整合。后续若需要互调功能，应另起 ADR、权限审查和跨仓库兼容性测试。
