# 安装、恢复与升级

## 只安装运行包

仓库中的技能目录是 `skill/human-rlaif/`。只复制这个目录到宿主认可的位置，最终布局为：

```text
<宿主 Skills 目录>/human-rlaif/
  SKILL.md
  LICENSE
  references/
  assets/
  scripts/workspace.py
```

同时保留 LICENSE，以便单独安装时携带 MIT 许可声明。不要把仓库根目录、论文、评测、tests 或开发验证脚本当成运行包。目录名和 frontmatter name 均为 human-rlaif。外部研究入口使用公开链接，安装后不依赖仓库其他文件。

执行安装前阅读本包及脚本，确认宿主和目标绝对路径。未指定目标时只提建议，获得确认后才复制；已在本会话明确授权的范围无需重复确认。检查目标是否存在，存在则停止并保留文件，请人选择新目录或授权升级，不能覆盖或移动已有技能。合成测试授权仅限指定测试沙盒。不得顺带修改 AGENTS.md、全局规则或其他技能。

分别报告：公共文件已放置、宿主已识别技能、实际首轮已完成；逐项验证，不能合并宣称“全部可用”。中英文触发词的存在只证明描述已写，真正识别需要宿主实际调用观察。

## 三步练习与渐进持久化

无需先填长表即可开始：人的判断与结果概率 → AI 一个挑战 → 约定新题复测日期。完整 HUMAN 和基线表等完成 2–3 个小循环后由 AI 起草、人确认。第一轮就保留真实输入、未知、反馈前首稿和现实责任。

只有需要跨会话保存时才请求私人目录和写入范围。说明 `init` 将创建 HUMAN.md、BASELINE.md、STATE.md、JOURNAL.md、events/ 和格式标记；这些模板是 draft，不要求当场填满，也不代表已经接受协议。安装授权不等于私人记录、公开上传或第三方发送授权。

## 命令

Python 3.10+ 可从已安装技能目录运行：

```bash
python scripts/workspace.py init --workspace /absolute/private/path
python scripts/workspace.py doctor --workspace /absolute/private/path
python scripts/workspace.py record --workspace /absolute/private/path --event /absolute/path/event.json
python scripts/workspace.py due --workspace /absolute/private/path
python scripts/workspace.py calibration --workspace /absolute/private/path
python scripts/workspace.py export --workspace /absolute/private/path --output /absolute/private/export.json
```

在本仓库根目录开发时，把命令中的脚本路径换成 `skill/human-rlaif/scripts/workspace.py`。`due --as-of 2026-10-24T09:00:00Z` 可以按指定时间检查到期情况；演示时间不能当成真实七天观察。

没有 Python 时按模板手工管理；没有持久文件能力时使用会话内记录，并提供可复制的续接卡。`doctor` 只检查本地结构，不能验证宿主自动加载、用户同意、真实来源或学习效果。

## 私密、初始化失败与恢复

私人工作区必须位于所有 Git 工作树之外，并避免 iCloud、Dropbox、OneDrive、Google Drive 等自动同步目录。同步服务或云模型可能处理其中内容，文件权限不等于完整的数据隔离。脚本拒绝已有符号链接路径，支持的 POSIX 环境创建目录 0700、文件 0600。

`init` 已有完整工作区时不覆盖；未知或残缺目录拒绝覆盖。新建失败时回滚本次创建的内容，保留预先存在的目录与文件；失败会报错；若有残留先检查归属，不能默认删除。新会话实际读取同一目录后才能称已恢复。

`record` 保存独立事件并拒绝重复 ID；HUMAN 仍为 draft 时警告，但允许记录真实的早期小循环。脚本不擅自改 HUMAN、BASELINE、STATE 或 JOURNAL。旧 v1 工作区与事件继续可读，新增字段的规则见 [事件格式](event-schema.md)；无原地数据迁移或静默覆盖。

`record` 通过独占 `.record.lock` 串行写入，并发写入会报错。进程异常退出可能留下锁；先确认没有写入进程，再人工检查并清理该锁后重试。脚本不会自动移除预先存在或归属不明的锁。

## 脱敏导出与移除

`export` 只输出允许的分类/数值字段，替换事件 ID，并省略自由文本、来源、路径和精确时间。它是数据最小化工具，不能保证匿名：少量罕见组合仍可能让人被识别。先在本地审查导出文件，确认目的、接收方与材料范围后再上传；命令本身不联网、不分享。目标文件必须是获准的本地绝对路径，已有文件拒绝覆盖。

升级前备份公共技能包与获准的私人状态，再明确授权替换公共包。版本不兼容时先制定迁移方案。移除只涉及公共技能包；私人记录的保留、导出或删除由人决定。

## 官方格式与宿主说明

- [Agent Skills 规范](https://agentskills.io/specification)
- [Codex Skills 官方说明](https://developers.openai.com/codex/skills/)

目录和调用方式以具体宿主当前说明及实际检测为准。
