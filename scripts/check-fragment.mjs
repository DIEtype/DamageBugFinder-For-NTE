import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../src/app.fragment.html', import.meta.url), 'utf8');
const match = source.match(/<script>\s*([\s\S]*?)<\/script>/);

if (!match) {
  throw new Error('No script block found in src/app.fragment.html');
}

new Function(match[1]);

const criticalMultiplierRule = "critDamage: 1 + (enabled('base-crit') ? percent('cdc-crit') : 0)";
if (!source.includes(criticalMultiplierRule)) {
  throw new Error('Panel critical damage must include the implicit base multiplier of 1');
}

const requiredRules = [
  "creationBase: 9000",
  "turbidBase: 2700",
  "darkstarBase: 45000",
  "fusionDivisor: 600",
  "specialBaseMultiplier: 1.2",
  "specialFusionCoefficient: 0.2",
  "specialFusionOffset: 180",
  "inclinationBase: 3603",
  "inclinationCapDivisor: 3",
  "if (target.model === 'creation')",
  "else if (target.model === 'turbid')",
  "else if (target.model === 'darkstar')",
  "push('defense', '防御区', 1, '黯星无视防御，防御乘区固定为 1')",
  "push('dot', '持续伤害区', state.dotDamageZone)",
  "atom.scopeMode === 'custom' && scopeAppliesToSkill(atom, target)",
  "if (component === 'damage') explicitDamageBonus += value",
  "const targetTag = target.model === 'turbid' ? 'dot' : target.tag",
  "if (atom.scopeMode === 'dot') return targetTag === 'dot'",
  "if (target.critical) push('crit', '暴击区', state.critZoneEnabled ? state.critDamage : 1)",
  "Math.max(0, Math.min(360, number('cdc-fusion')))",
  "state.fusionStrength = state.fusionBase * (1 + state.fusionPercent) + state.fusionFlat",
  "function specialZoneMultiplier(fusionStrength)",
  "formulaSettings.specialBaseMultiplier",
  "formulaSettings.specialFusionCoefficient * fusionStrength",
  "formulaSettings.specialFusionOffset + fusionStrength",
  "if (specialEffect === 'infusion')",
  "target.model === 'skill' && specialEffect === 'overlay'",
  "overlayExtraPrediction(exact, state.overlayFusionCoefficient, factors, state.overlayPursuitRatio, state.overlayPursuitBonus)",
  "label: '覆纹额外比例'",
  "overlaySource: true",
  "覆纹应有附加伤害",
  "灵可·覆纹追击强化",
  "狂暴溯源拆分验证",
  "overlayPursuitRatio: normalOverlayPursuitRatio()",
  "overlayPursuitBonus: 0",
  "effect.effectKind === 'lingke-overlay'",
  "schema: 15",
  "data-special-effect-option=\"infusion\"",
  "data-special-effect-option=\"overlay\"",
  "function componentAffectsDamageTarget(component, effect, target, contributors = [])",
  "function inclinationPrediction(state, contributors)",
  "function inclinationBaseShredByAttribute(contributors)",
  "resShred: sharedBaseShred[contributor.attribute] || 0",
  "resIgnore: contributor.resIgnore",
  "penetration: contributor.penetration",
  "function inclinationShredApplies(effect, contributor, contributors)",
  "const inclinationEffects = effectRowsForWorkspace('inclination').map(serializeEffectRow)",
  "INCLINATION_PRESET.cap / formulaSettings.inclinationCapDivisor",
  "function resistanceZoneMultiplier(baseResistance, resistanceIgnore = 0, resistanceShred = 0)",
  "const effectiveResistance = baseResistance - resistanceIgnore - resistanceShred",
  "1 - effectiveResistance / (1 - effectiveResistance)",
  "resistanceZoneMultiplier(percent('cdc-resistance'), state.resIgnore, state.resShred)",
  "resistanceZoneMultiplier(\n            INCLINATION_PRESET.resistances[contributor.attribute]",
  "resIgnore: enabled('base-res-ignore') ? percent('cdc-res-ignore') : 0",
  "Math.round(exact)",
  "if (effect.searchState === 'suspended') return []",
  "searchState: normalizedEffectSearchState(row.querySelector('[data-effect-search-state]').value)",
  "const forcedActive = (atom.kind === 'base' && verificationMode !== 'rage') || atom.searchState === 'locked'",
  "const minimumCount = layers[0]?.searchState === 'locked' ? 1 : 0",
  "const atoms = createAtoms(effects, skills, heals, contributors)",
  "if (model === 'turbid') return 'dot'",
  "return model === 'skill' && row.querySelector('[data-skill-tag]').value === 'dot' ? 'dot' : 'direct'",
  "return sum + inactiveRatio * (effect.priority ? 2 : 1)",
  "|| a.priorityPenalty - b.priorityPenalty",
  "function buildSearchDimensions(atoms)",
  "options.push(layers.slice(0, count).map((layer) => layer.id))",
  "stackEnabled: row.querySelector('[data-effect-stack-enabled]').checked",
  "text.includes('reaction_1') || text.includes('reaction1_')",
  "text.includes('reaction_5')",
  ".filter((group) => selectedRows.has(group.id) && group.single_hit)",
  "result.integration_mode === 'axis_v1'",
  "AXIS · 1 HIT",
  "saveCaptureTarget(group, event.target.value)",
  "function captureEvidenceKey(group = {})",
  "function captureReplay(group, targetValue, knowledge, replayCache = null)",
  "function scoreCaptureReplay(base, group)",
  "data-capture-replayable",
  "只选可还原",
  "按当前面板重算",
  "const OFFICIAL_SKILL_DATABASE = /*__OFFICIAL_SKILL_DATABASE__*/ null",
  "function officialSkillMatch(group = {})",
  "function captureEventFamily(group = {})",
  "function captureKnowledge(group = {})",
  "cdc-capture-skill-level",
  "placeholder=\"玩家填写\"",
  "技能等级待玩家设置",
  "技能等级未设置，因此未自动填写倍率",
  "角色表精确匹配",
  "临时分类",
  "使用教学 / GUIDE",
  "公式教学",
  "game-calculator-guided-tour-completed-v1",
  "game-calculator-guided-tour-mode-seen-v1-",
  "advanceTourAfterControl",
  "width: min(1560px, calc(100vw - 32px))",
  "width: min(1440px, calc(100vw - 32px))",
  "flex-wrap: wrap",
  "data-formula-help",
  "function formulaHelpForFactor(element)",
  "<mfrac>",
  "cdc-formula-tooltip",
  "popover=\"manual\"",
  "tooltip.showPopover()",
  "function startOperationTour(type = workspaceMode, startIndex = 0)",
  "function formulaGuidePages()",
  "function tourStepsForType(type)",
  "title: '填写攻击与治疗基础面板'",
  "title: '先确认倾陷敌人与小队规则'",
  "倾陷不读取当前角色的普通攻击面板，也不使用 OCR",
  "tourType = workspaceMode",
  "cdc-tour-action",
  "lastVisible: true",
  "target: '#cdc-add-effect'",
  "target: '#cdc-add-skill'",
  "target: '#cdc-add-inclination-contributor'",
];
for (const rule of requiredRules) {
  if (!source.includes(rule)) throw new Error(`Missing calculation rule: ${rule}`);
}

if (/id="cdc-capture-skill-level"[^>]*\bvalue="13"/.test(source)) {
  throw new Error('Capture skill level must default to unset because packet capture does not identify it');
}

const closeTo = (actual, expected) => Math.abs(actual - expected) < 1e-10;
const overlayFunctionMatch = source.match(/function overlayExtraPrediction\([\s\S]*?\n      }\n      let formulaSettings/);
if (!overlayFunctionMatch) throw new Error('Unable to extract overlayExtraPrediction');
const overlayFunctionSource = overlayFunctionMatch[0].replace(/\n      let formulaSettings[\s\S]*$/, '');
const overlayExtraPrediction = new Function('format', `${overlayFunctionSource}; return overlayExtraPrediction;`)((value) => String(value));
const fusionCoefficientAt360 = 1 + (0.2 * 360) / (180 + 360);
const overlayCase = overlayExtraPrediction(10000, fusionCoefficientAt360, [{ kind: 'skill', label: '技能倍率', value: 1 }], 0.2, 0);
if (!closeTo(overlayCase.ratio, 0.36) || !closeTo(overlayCase.exact, 3600) || overlayCase.displayed !== 3600) {
  throw new Error('Normal overlay must equal base damage × ([C(H)-1] + 20%×C(H))');
}
const lingkeOverlayCase = overlayExtraPrediction(10000, fusionCoefficientAt360, [], 0.3, 0.1);
if (!closeTo(lingkeOverlayCase.ratio, 0.5073333333333333)
  || !closeTo(lingkeOverlayCase.exact, 5073.333333333333)) {
  throw new Error('Lingke overlay must equal base damage × ([C(H)-1] + 30%×C(H)×1.1)');
}
if (overlayCase.formula.at(-1)?.label !== '覆纹额外比例') {
  throw new Error('Overlay formula trace must append the derived extra-damage ratio');
}

const resistanceFunctionMatch = source.match(/function resistanceZoneMultiplier\([\s\S]*?\n      }/);
if (!resistanceFunctionMatch) throw new Error('Unable to extract resistanceZoneMultiplier');
const resistanceZoneMultiplier = new Function(`${resistanceFunctionMatch[0]}; return resistanceZoneMultiplier;`)();
if (!closeTo(resistanceZoneMultiplier(0.2, 0, 0).multiplier, 0.8)) {
  throw new Error('Positive effective resistance branch is incorrect');
}
if (!closeTo(resistanceZoneMultiplier(0.2, 0, 0.24).multiplier, 1.0384615384615385)) {
  throw new Error('Negative effective resistance branch is incorrect');
}
if (!closeTo(resistanceZoneMultiplier(0.2, 0.1, 0.1).multiplier, 1)) {
  throw new Error('Zero effective resistance boundary is incorrect');
}

const inclinationShredMatch = source.match(/function inclinationBaseShredByAttribute\([\s\S]*?\n      }/);
if (!inclinationShredMatch) throw new Error('Unable to extract inclinationBaseShredByAttribute');
const inclinationBaseShredByAttribute = new Function(`${inclinationShredMatch[0]}; return inclinationBaseShredByAttribute;`)();
const sharedShred = inclinationBaseShredByAttribute([
  { enabled: true, attribute: 'dark', resShred: 0.12 },
  { enabled: true, attribute: 'dark', resShred: 0.12 },
  { enabled: true, attribute: 'curse', resShred: 0.05 },
  { enabled: false, attribute: 'dark', resShred: 0.2 },
]);
if (!closeTo(sharedShred.dark, 0.24) || !closeTo(sharedShred.curse, 0.05)) {
  throw new Error('Inclination resistance shred must stack by attribute and ignore disabled contributors');
}

const inclinationShredScopeMatch = source.match(/function inclinationShredApplies\([\s\S]*?\n      }/);
if (!inclinationShredScopeMatch) throw new Error('Unable to extract inclinationShredApplies');
const inclinationShredApplies = new Function(`${inclinationShredScopeMatch[0]}; return inclinationShredApplies;`)();
const scopeContributors = [
  { id: 'a', enabled: true, attribute: 'dark' },
  { id: 'b', enabled: true, attribute: 'dark' },
  { id: 'c', enabled: true, attribute: 'curse' },
];
const darkOnlyEffect = { inclinationScopeMode: 'custom', inclinationContributorIds: ['a'] };
if (!inclinationShredApplies(darkOnlyEffect, scopeContributors[1], scopeContributors)
  || inclinationShredApplies(darkOnlyEffect, scopeContributors[2], scopeContributors)) {
  throw new Error('Custom inclination shred must expand to contributors of the selected attribute only');
}

const inclinationDefense = 180 / (180 + 190);
const inclinationCapZone = 70 / 3;
const screenshotTeamExact = 3603 * inclinationCapZone * inclinationDefense * (
  5.6 * resistanceZoneMultiplier(0.2, 0.12, 0).multiplier
  + 4.14 * resistanceZoneMultiplier(0.2, 0.12, 0).multiplier
  + 4.12 * resistanceZoneMultiplier(0.16, 0, 0).multiplier
);
if (Math.round(screenshotTeamExact) !== 508030) {
  throw new Error('Inclination personal ignore/penetration regression: expected screenshot case to display 508030');
}

if (/fusion_strength:\s*\{\s*label/.test(source)) {
  throw new Error('Fusion strength must not be an OCR import target');
}

console.log('Fragment JavaScript syntax and calculation rules: OK');
