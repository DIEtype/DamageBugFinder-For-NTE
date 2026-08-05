# 计算公式

所有百分数在计算时转换为小数。例如 20% 使用 `0.2`，240% 使用 `2.4`。

## 战斗面板攻击

设：

- `A_panel`：非战斗面板攻击；
- `A_base`：基础攻击；
- `B_attack`：生效的战斗攻击加成总和。

```text
A_combat = A_panel + A_base × B_attack
```

觉醒和武器提供的攻击力加成会先加入 `B_attack`，再乘以基础攻击。已经包含在非战斗面板中的加成不应重复填写。

## 防御区

```text
Defense = (100 + CharacterLevel)
          / [(100 + CharacterLevel)
          + (100 + EnemyLevel) × (1 - DefensePenetration)]
```

## 抗性区

```text
Resistance = 1 - BaseResistance + ResistanceShred
```

## 增伤区

```text
DamageBonus = 1
              + GeneralBonus
              + ElementalBonus
              + ExtraBonus
              + ActiveAwakeningAndWeaponBonus
```

## 技能倍率区

加算效果先相加，乘算效果随后连乘：

```text
SkillMultiplier = (BaseMultiplier + Σ AdditiveMultiplier)
                  × Π (1 + MultiplicativeMultiplier)
```

例如基础倍率为 240%，额外提高 30%：

- 加算：`2.4 + 0.3 = 2.7`；
- 乘算：`2.4 × 1.3 = 3.12`。

## 常规伤害

最终环合强度按百分比提升后再加固定值：

```text
FusionStrength = BaseFusionStrength × (1 + Σ FusionPercentBonus)
                 + Σ FusionFlatBonus
```

`BaseFusionStrength` 是非战斗面板值，合法范围为 `0～360`。该上限不限制觉醒、武器等 Buff 作用后的 `FusionStrength` 最终值。

启用浸染或覆纹时，两者使用同一个独立乘区；一次验算只选择其中一种：

```text
SpecialBonus = 20% + FusionStrength / 1400
InfusionOrOverlay = 1 + SpecialBonus
                  = 1.2 + FusionStrength / 1400
```

其中 `FusionStrength` 是本次验算假设下的最终环合强度，包含当前生效 Buff 提供的百分比提升和固定数值提升；它不是只读取基础面板值。未启用浸染或覆纹时 `InfusionOrOverlay = 1`。

游戏面板显示的是额外暴击伤害，计算器输入框和 OCR 均保留这个面板原值。实际暴击倍率为：

```text
CriticalDamageMultiplier = 1
                           + PanelCriticalDamage
                           + Σ ActiveCriticalDamageBonus
```

例如面板显示 `134%`，且没有其他暴击伤害 Buff，则实际暴击倍率为 `1 + 1.34 = 2.34`。

非暴击：

```text
NormalDamage = A_combat
               × Defense
               × Resistance
               × DamageBonus
               × SkillMultiplier
               × InfusionOrOverlay
```

暴击：

```text
CriticalDamage = NormalDamage × CriticalDamageMultiplier
```

## 创生花伤害

非暴击：

```text
CreationDamage = 9000 × 1 × Defense × Resistance
                 × (1 + FusionStrength / 600)
                 × ExplicitReactionDamageBonus
```

暴击：

```text
CriticalCreationDamage = CreationDamage × CriticalDamageMultiplier
```

创生花不读取面板攻击、默认常规增伤区、普通技能倍率、持续伤害强化、浸染或覆纹乘区。

## 浊燃伤害

浊燃与创生花使用相同的防御、抗性和环合强度修正，但固定基础值为 `2700`，并且可以暴击。浊燃固定视为持续伤害。

```text
TurbidDamage = 2700 × 1 × Defense × Resistance
               × (1 + FusionStrength / 600)
               × (1 + ActiveDamageOverTimeBonus)
               × ExplicitReactionDamageBonus

CriticalTurbidDamage = TurbidDamage × CriticalDamageMultiplier
```

浊燃不读取面板攻击、默认常规增伤区、普通技能倍率、浸染或覆纹乘区。

## 黯星伤害

黯星固定基础值为 `45000`，防御乘区始终为 `1`，即无视角色、敌人等级与防御穿透变化：

```text
DarkstarDamage = 45000 × 1 × Resistance
                 × (1 + FusionStrength / 600)
                 × ExplicitReactionDamageBonus

CriticalDarkstarDamage = DarkstarDamage × CriticalDamageMultiplier
```

黯星不读取面板攻击、普通技能倍率、持续伤害强化、浸染或覆纹乘区。

## 环合反应的指定增伤

创生花、浊燃和黯星默认都不读取面板与“作用全部技能”的常规增伤。只有把某个 Buff 的作用范围设为“自定义技能”，并明确勾选对应环合反应时，该 Buff 的“增伤”字段才形成：

```text
ExplicitReactionDamageBonus = 1 + Σ ExplicitlySelectedDamageBonus
```

“全部技能”“仅持续伤害”或“仅非持续伤害”不会触发这个覆盖规则。攻击加成、普通技能倍率、浸染和覆纹乘区即使来自同一个 Buff，也仍不进入环合反应公式。

## 持续伤害 Tag 与 Buff 作用范围

“持续伤害”是常规伤害的 Tag，计算公式与其他常规技能完全相同。它可以作为 Buff 作用范围条件。

每个 Buff 可配置为：全部伤害技能、仅持续伤害、仅非持续伤害或自定义技能。Buff 的全局生效/失效状态仍由整批数据共同决定；若该 Buff 生效，它的数值只会加入符合所设范围的技能。环合反应仍先遵守各自的乘区白名单，只有上节所述的“自定义点名增伤”可以覆盖默认增伤排除。

搜索维度会在验算前按公式白名单裁剪。某个 Buff 属性必须至少影响一个已启用的验算技能或狂暴溯源候选来源，才会进入排列。例如只验算浊燃时，Buff 中的攻击、普通技能倍率和非自定义点名增伤不会生成无意义的生效/失效组合；作用范围不覆盖任何当前技能的 Buff 也会被跳过。

## 叠层 Buff

普通 Buff 默认仍按单次效果处理。只有开启“叠层 Buff”后，该行所有非零属性才解释为每层数值，并共享同一个层数：

```text
StackedComponentValue = PerStackValue × ActiveStackCount
```

技能倍率选择乘算时，同一叠层 Buff 先合并层数，再形成一个独立乘算项：

```text
StackedMultiplicativeSkillBonus = 1 + PerStackBonus × ActiveStackCount
```

因此每层提高 6%、当前 4 层时为 `1 + 0.06 × 4 = 1.24`，不会计算为 `1.06^4`。不同 Buff 的乘算项仍互相连乘。

“自动反推”把 `0～最大层数` 作为互斥离散状态；“固定层数”只比较指定层数正常生效和整项未生效。高触发优先只倾向层数大于 0，不强制偏向满层；测量误差始终优先于该偏好。若 Buff 设为“锁定生效”，自动反推范围改为 `1～最大层数`；固定层数最低为 1。

## 治疗量

```text
Healing = A_combat × HealingMultiplier × (1 + HealingBonus)
```

`HealingBonus` 为基础治疗加成与已生效觉醒、武器等候选治疗加成之和。伤害技能和治疗技能分别记录、分别计算；治疗不读取防御、抗性、增伤、暴击、浸染或覆纹乘区。

## 精确值和显示值

内部计算保留小数。游戏显示值只在最终结果处四舍五入：

```text
DisplayedValue = round(ExactValue)
```

反向验算使用显示值误差，并且只报告每条实测数据误差不超过 ±20 的来源或状态。

## 结果字段与状态排序

一次验算中的“全局状态”会用于本批全部实测数据，而不是为每条实测值分别切换增益。常规伤害与治疗验算固定基础区，只反推相关 Buff；狂暴溯源才额外包含相关基础乘区的生效/失效假设。

单项显示值误差：

```text
ItemError = |round(ExactValue) - ObservedValue|
```

“±20 内来源数”只用于狂暴溯源，表示在当前全局状态下，该条未知伤害有多少个“技能、暴击状态、倍率来源”的组合满足 `ItemError ≤ 20`。这个数字越大，说明该条伤害存在越多歧义，不代表全局状态更可信。

全局状态依次按以下规则从优到劣排序：

1. 超过 ±20 或没有来源的条目数更少；
2. `Σ(ItemError / max(1, ObservedValue))` 更小；
3. 基础乘区失效数更少（仅狂暴溯源存在此维度）；
4. 误用其他技能倍率的条目数更少；
5. Buff 优先级违背值更小；
6. 觉醒和武器效果失效数更少。

常规验算只汇报全部条目均满足 ±20 的状态。狂暴溯源先选择无来源条目最少的状态，再比较其余排序项；超限条目会显示为“无来源”，不会强行给出差距很大的匹配。

顶部“最符合实测的全局状态”始终显示排序第一的解释，因此在没有完美匹配时也能用于诊断。右侧“零误差全局状态”只显示 `TotalDisplayError = 0` 且没有无来源条目的状态；带误差的备选解释不会列出。该顺序是规则驱动的解释优先级，不代表经过统计建模得到的概率。

“高触发优先”不会改变搜索空间，也不会把未勾选 Buff 当作默认失效。搜索仍从全部生效开始；只有在误差、基础失效和倍率来源等主要条件相同的解释之间，程序才更优先保留已勾选 Buff 生效的状态。完整失效一个勾选 Buff 的优先级违背权重为 `2`，未勾选 Buff 为 `1`；部分失效按该 Buff 失效项占比计算。

Buff 的验算状态是更强的约束：`参与搜索`保留原有组合逻辑；`锁定生效`强制所有相关属性进入公式；`挂起排除`不创建原子和搜索维度。锁定或挂起时，“高触发优先”不再参与该 Buff 的排序。

## 失效假设

常规验算会考虑与当前公式相关的 Buff 生效、部分失效、叠层层数及技能倍率误用。只有狂暴溯源额外考虑与候选来源公式相关的基础区失效：

- 基础攻击加成未生效；
- 基础防御穿透未生效；
- 基础抗性削弱未生效；
- 通用、属性或额外增伤未生效；
- 基础暴击伤害未生效；
- 基础环合强度未生效；
- 浸染 / 覆纹独立乘区未生效；
- 防御区、抗性区、增伤区、暴击区、技能倍率区或环合修正区整体未生效。

觉醒和武器等 Buff 的全部失效、部分失效仍由常规验算与狂暴溯源共同检查，但挂起 Buff 会跳过，锁定 Buff 不允许失效。

搜索默认从相关基础乘区和参与搜索的 Buff 全部生效、叠层 Buff 满层的状态开始，再按模式与约束逐项排除。常规模式的基础区以及锁定 Buff 始终保持生效。

## 搜索覆盖范围

搜索强度决定完整枚举的判断项上限和超过上限后的限宽：

| 档位 | 完整枚举上限 | 限宽 |
| --- | ---: | ---: |
| 标准 | 18 | 5,000 |
| 深度 | 20 | 20,000 |
| 极限 | 22 | 50,000 |

普通二元判断项产生 `2^N` 个状态；每个自动叠层 Buff 额外乘以 `(最大层数 + 1)`。例如 10 个普通判断项与一个最多 6 层的 Buff 共 `2^10 × 7 = 7168` 个状态。总状态数不超过所选档位对应的 `2^上限` 时，程序会完整枚举。为了控制内存，只在线保留排序最好的 300 个解释。

总状态数超过上限时，程序从“普通 Buff 全生效、叠层 Buff 满层”开始逐维搜索，并在每一层保留最优的限宽路径。每个层数仍作为一个整体候选参与比较；限宽搜索不是完整枚举，不能保证覆盖全部理论状态。
