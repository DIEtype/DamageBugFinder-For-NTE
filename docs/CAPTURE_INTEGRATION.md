# 抓包接入设计

## 第一阶段：标准 Sidecar（当前实现）

计算器通过 JSON-RPC 2.0 / NDJSON 启动用户指定的：

```text
nte-core.exe serve --stdio --data-dir <本机应用数据目录>
```

完成 `core.hello`、`capture.detect` 和 `capture.start` 后，消费 `event.battle.summary`，同时显式使用 `raw_capture: enabled`。Core 通过 `core.status.raw_capture_path` 返回本机 PCAPNG 路径，计算器只增量读取已经完整写入的数据块，不重复扫描整个文件。

战斗摘要是累计值。桌面桥按角色、技能名称、类别、Ability、GameplayEffect 和追加伤害标记建立稳定键，再用相邻摘要的 Hit 与伤害差值产生事件组。

- Hit 差值为 1：可作为一条实测显示伤害。
- Hit 差值大于 1：只能视为短间隔多段合计，不允许自动拆分。
- `Reaction_1`：创生花候选。
- `Reaction_5`：浊燃候选。

人工确认的“来源事件 → 计算器技能”关系按角色和版本保存在浏览器本地存储。测试服出现未知 GA/GE 时，不依赖旧数据库也能建立新映射。

## 标准接口的边界

标准 Sidecar 明确不通过 stdout 输出逐击、PacketDebug、payload、端点或 PCAP 内容，战斗摘要也没有可靠的暴击标记。计算器的本机 PCAP 适配器只保留经过连续 UE 包序号确认的游戏流，从 8 种位对齐中发现 `Melee`、`Skill`、`Reaction`、`CritDamage`、`GA_`、`GE_` 等可读名称；原始载荷和网络端点不会进入前端。

事件前后 `-0.12..+0.35` 秒内近似整数的浮点值只作为“候选数值”。用户填写游戏显示伤害后，前端按 `±20` 过滤和排序；在新伤害结构得到确认前，不得将候选值自动标记为正式 damage、critical 或 segment 字段。

标准接口仍不包含 GameplayEffect 的 apply/remove/stack 生命周期，因此当前版本不能声称已经自动读取 Buff。

Buff 数值、作用技能、叠层规则及候选生效状态仍由计算器维护。这样即使测试服数据尚未进入公开数据库，验算功能也不受影响。

## 第二阶段：测试服事件学习适配器（预留）

后续若有合法可用的逐击/效果事件源，应通过独立适配器输出最小化的本地事件，不改动公式层：

```json
{"kind":"damage","event_id":"...","ability":"GA_...","effect":"GE_...","value":4413,"critical":null,"segment":null}
{"kind":"effect_apply","event_id":"...","effect":"GE_...","target":"self","stacks":1}
{"kind":"effect_stack","event_id":"...","effect":"GE_...","stacks":4}
{"kind":"effect_remove","event_id":"...","effect":"GE_...","target":"self"}
```

设计约束：

1. 未知字段使用 `null`，不得从伤害值强行猜测暴击、段数或 Buff。
2. 原始 payload、账号身份和网络端点不进入计算器。
3. 多段技能先保留逐击，再由测试员选择某一段或手工建立分段规则。
4. Buff 事件只能收窄候选状态，数值仍以测试员填写的文本描述为准。
5. 第三方 AGPL 组件与本项目 MIT 代码保持独立进程及独立分发。
6. 原始 PCAP 只保存在 `%LOCALAPPDATA%\GameDamageCalculator\capture`，不应提交到仓库、公开 Issue 或测试报告。
