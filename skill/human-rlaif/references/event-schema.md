# 事件格式 v2 / Event schema v2

事件是不可覆盖的 JSON 记录。`record` 输入与磁盘上的已保存事件格式不同：输入不含 `schema_version` 或 `recorded_at`，脚本保存时生成这两个字段。未知键一律拒绝，不静默忽略；拼写错误、重复 JSON 键和不完整字段组会报错。未知可选值省略，基本文本可用 unknown/pending，不能编造时间或结果。

## 兼容 v1

九个基本字段保持不变：`id`、`mode`、`human_input`、`ai_feedback`、`human_response`、`action`、`reality_feedback`、`evidence_status`、`sources`。

- `id`：1–80 位小写字母、数字或连字符，以字母或数字开头；重复 ID 拒绝。
- `mode`：production / learning / assessment。
- 五个文本字段：非空字符串；缺失实际信息用 unknown/pending。
- `evidence_status`：pending / reported / externally_checked。externally_checked 需要非空 `sources` 和不是 unknown/pending 的现实反馈；来源真实性仍需人核查。
- `sources`：获准保存的来源指针字符串列表，可为空；不应包含秘密或未经授权的个人资料。

磁盘中的 v1 事件包含基本字段、`recorded_at` 和 `schema_version: 1`，可继续读取且不改写旧字节。已有 v1 工作区的格式标记不自动升级。纯九字段输入在任何工作区都保存为 v1，包括新建的 v2 工作区；含任意新增字段的输入保存为 v2。工作区版本不自动把缺少时间证据的旧格式事件升级为 v2。磁盘事件的版本必须明确为 1 或 2；v1 不能混入 v2 扩展。

已保存文件不能直接作为 `record` 输入重放：存储元数据会被拒绝，同 ID 也不会覆盖。新事件需要新 ID、移除存储元数据，并保留真实的事件关系，不复制假冒新的独立样本。

## v2 可选任务与复测字段

| 字段 | 类型与规则 |
|---|---|
| task_type | 非空字符串，任务族，例如 content-judgment |
| assistance | none / hint / critique / rewrite / solution / other / unknown；记录本轮帮助，首稿何时获得帮助另在正文说清 |
| isolation | clean / partial / contaminated / unknown；独立性判据见运行协议 |
| rubric_ref | 非空字符串，作答前锁定的标准版本或来源指针；脚本不锁定外部文件 |
| retest_interval | 正整数，单位为天；必须同时提供 due_at，不自动推算日期 |
| due_at | 含秒与时区的 RFC3339 日期，例 2026-10-24T09:00:00Z；若有 ai_feedback_at，必须晚于它 |
| human_draft_at | 首稿保存时间，与 ai_feedback_at 成对提供 |
| ai_feedback_at | 首次目标反馈时间；统一为 UTC 后必须严格晚于 human_draft_at，不能相等 |
| retest_of | 指向已有且含 due_at 的事件 ID；任何模式都必须提供成对首稿/反馈时间，复测首稿不得早于原 due_at；实际保存时间须已到期且晚于原事件保存时间；同一安排只能完成一次 |

时间字段都要求日期、秒、明确时区，可用 Z 或 ±HH:MM；最多六位小数秒。human_draft_at 与 ai_feedback_at 必须成对，首稿严格早于反馈，保存时两个时间都不得晚于 recorded_at；不能提前保存未来“首稿”。时间值只是声明，不能证明真实独立性。

以下情况必须有这对时间：含新增字段的 v2 learning/assessment 事件；任何模式下的预测、isolation=clean 或 retest_of。纯九字段的 v1 兼容记录允许省略；production 事件在没有预测、clean 或 retest_of 时也可省略。读取已存的 v2 learning/assessment 事件也一律要求这对时间。非预测并不自动豁免学习/评估时间要求。缺失的历史时间继续缺失，不能为了通过校验补造。

`due` 只列出查询时已保存、已到期且没有当时已保存的有效完成记录的事件；按 UTC 到期时间再按 ID 排序。无目标、提前或重复等无效完成关联列在 invalid_completions，不能用它们隐藏原到期项。`retest_of` 的合法性检查不等于确认人真的做了新题。

## 预测与结果

预测必须同时包含：

| 字段 | 规则 |
|---|---|
| prediction_type | 当前仅 binary |
| prediction | 非空、可观察的预期结果陈述，含观察范围与期限 |
| confidence | 0–100 的有限数字百分比，表示这条陈述成立的概率；不能用 true/false 或字符串 |
| resolution_criteria | 非空、事先约定的结果判据，写清何时、据什么判定发生或未发生 |

有预测就必须提供 human_draft_at 与 ai_feedback_at。具体示例在 [event.example.json](../assets/event.example.json)；其中全部内容和时间均为合成，结果仍 pending。

后来保存单独的结果事件，九个基本字段照常填写，再加一对字段：`resolves_prediction` 为原预测 ID，`outcome` 为 JSON true 或 false。结果事件必须 externally_checked，具有实际反馈与来源，且保存时间严格晚于原预测；不允许同一预测被重复解答或引用自身。无结果时不提交 outcome，不用 false 或 null 代替未知。如果只是补录现实结果，没有新的练习或反馈，可用 production 结果事件并省略人机时间；learning/assessment 结果事件仍须满足上述时间规则，不能编造一次未发生的反馈。

校准只对有效预测和唯一的后续结果配对计分；无结果列为 unresolved，异常引用或重复结果不当成命中。命中率的判断阈值为 p≥0.5，Brier 为平均 `(p-y)²`。固定概率分档为 [0,.2)、[.2,.4)、[.4,.6)、[.6,.8)、[.8,1]；空样本指标为 null。参见 [预测校准协议](protocol.md#预测校准主指标)。

## 草案警告与导出

HUMAN.md 仍为 draft 时，`record` 给出警告但可保存事件，支持先完成 2–3 个小循环再确认完整协议。没有 draft 字样也不能据此推断本人接受。

`export` 只输出分类/数值白名单和替代 ID，省略正文、预测陈述、判据、task_type、rubric_ref、来源和精确时间。这个副本不能直接导回完整事件，也不是匿名性证明；上传前需要人工审核和单独授权。
