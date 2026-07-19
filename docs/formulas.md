# 异环NTE伤害计算公式

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

非暴击：

```text
NormalDamage = A_combat
               × Defense
               × Resistance
               × DamageBonus
               × SkillMultiplier
```

暴击：

```text
CriticalDamage = NormalDamage × CriticalDamageMultiplier
```

## 创生伤害

非暴击：

```text
CreationDamage = 9000 × Defense × Resistance
```

暴击：

```text
CriticalCreationDamage = CreationDamage × CriticalDamageMultiplier
```

创生伤害不读取面板攻击、常规增伤区或普通技能倍率。

## 治疗量

```text
Healing = A_combat × HealingMultiplier
```

伤害技能和治疗技能分别记录、分别计算。

## 精确值和显示值

内部计算保留小数。游戏显示值只在最终结果处四舍五入：

```text
DisplayedValue = round(ExactValue)
```

反向验算使用显示值误差，并且只报告每条实测数据误差不超过 ±20 的来源或状态。

## 结果字段与状态排序

一次验算中的“全局状态”包含所有基础乘区、觉醒和武器效果的生效/失效假设。同一候选全局状态会用于本批全部实测数据，而不是为每条实测值分别切换增益。

单项显示值误差：

```text
ItemError = |round(ExactValue) - ObservedValue|
```

“±20 内来源数”只用于狂暴溯源，表示在当前全局状态下，该条未知伤害有多少个“技能、暴击状态、倍率来源”的组合满足 `ItemError ≤ 20`。这个数字越大，说明该条伤害存在越多歧义，不代表全局状态更可信。

全局状态依次按以下规则从优到劣排序：

1. 超过 ±20 或没有来源的条目数更少；
2. `Σ(ItemError / max(1, ObservedValue))` 更小；
3. 基础乘区失效数更少；
4. 误用其他技能倍率的条目数更少；
5. 觉醒和武器效果失效数更少。

常规验算只汇报全部条目均满足 ±20 的状态。狂暴溯源先选择无来源条目最少的状态，再比较其余排序项；超限条目会显示为“无来源”，不会强行给出差距很大的匹配。

顶部“最符合实测的全局状态”始终显示排序第一的解释，因此在没有完美匹配时也能用于诊断。右侧“零误差全局状态”只显示 `TotalDisplayError = 0` 且没有无来源条目的状态；带误差的备选解释不会列出。该顺序是规则驱动的解释优先级，不代表经过统计建模得到的概率。

## 失效假设

反向验算会考虑：

- 基础攻击加成未生效；
- 基础防御穿透未生效；
- 基础抗性削弱未生效；
- 通用、属性或额外增伤未生效；
- 基础暴击伤害未生效；
- 防御区、抗性区、增伤区、暴击区、技能倍率区或治疗倍率区整体未生效；
- 觉醒和武器的各项提升全部失效或部分失效；
- 技能读取了其他已记录技能的倍率。

搜索默认从所有基础乘区、觉醒和武器效果全部生效的状态开始，再逐项排除。
