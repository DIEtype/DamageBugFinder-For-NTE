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
  "specialBaseBonus: 0.2",
  "specialFusionDivisor: 1400",
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
  "1 + formulaSettings.specialBaseBonus + state.fusionStrength / formulaSettings.specialFusionDivisor",
  "specialEffect === 'overlay' ? '覆纹区' : '浸染区'",
  "data-special-effect-option=\"infusion\"",
  "data-special-effect-option=\"overlay\"",
  "function componentAffectsDamageTarget(component, effect, target)",
  "if (effect.searchState === 'suspended') return []",
  "searchState: normalizedEffectSearchState(row.querySelector('[data-effect-search-state]').value)",
  "const forcedActive = (atom.kind === 'base' && verificationMode !== 'rage') || atom.searchState === 'locked'",
  "const minimumCount = layers[0]?.searchState === 'locked' ? 1 : 0",
  "const atoms = createAtoms(effects, skills, heals)",
  "if (model === 'turbid') return 'dot'",
  "return model === 'skill' && row.querySelector('[data-skill-tag]').value === 'dot' ? 'dot' : 'direct'",
  "return sum + inactiveRatio * (effect.priority ? 2 : 1)",
  "|| a.priorityPenalty - b.priorityPenalty",
  "function buildSearchDimensions(atoms)",
  "options.push(layers.slice(0, count).map((layer) => layer.id))",
  "stackEnabled: row.querySelector('[data-effect-stack-enabled]').checked",
  "text.includes('reaction_1') || text.includes('reaction1_')",
  "text.includes('reaction_5')",
  ".filter((item) => item.group?.single_hit)",
  "saveCaptureTarget(group, event.target.value)",
];
for (const rule of requiredRules) {
  if (!source.includes(rule)) throw new Error(`Missing calculation rule: ${rule}`);
}

console.log('Fragment JavaScript syntax and calculation rules: OK');
