import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

function argument(name, fallback = '') {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const inputPath = resolve(argument('--input', 'C:/Users/awayf/Downloads/角色属性.xlsx'));
const outputPath = resolve(argument('--output', `${projectRoot}/data/official-skill-segments.json`));

const sourceBytes = await readFile(inputPath);
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const characterRows = workbook.worksheets.getItem('角色').getRange('A1:L24').values;
const skillRows = workbook.worksheets.getItem('角色技能数值').getRange('A1:AB628').values;

function recordsFrom(values) {
  const headers = values[0].map((value) => String(value ?? '').trim());
  return values.slice(1).map((row, offset) => ({
    sourceRow: offset + 2,
    values: Object.fromEntries(headers.map((header, index) => [header, row[index]])),
  }));
}

const charactersByName = new Map();
const characters = recordsFrom(characterRows).map(({ values }) => {
  const character = {
    id: Number(values.ID),
    name: String(values['名称'] || '').trim(),
    codename: String(values['代号'] || '').trim(),
    attribute: String(values['异能属性'] || '').trim(),
  };
  if (!charactersByName.has(character.name)) charactersByName.set(character.name, []);
  charactersByName.get(character.name).push(character);
  return character;
});

function cleanText(value) {
  return value === null || value === undefined ? '' : String(value).trim();
}

function normalizeCategory(values) {
  const text = [values.AbilityKey, values.GEName, values['技能名称'], values['伤害来源分类'], values['描述']]
    .map(cleanText).join(' ');
  if (/同频合击|\bLTE\b|_LTE(?:_|$)/i.test(text)) return '同频合击';
  if (/\bQTE\b|_QTE(?:_|$)/i.test(text)) return '援护技';
  if (/UltraSkill/i.test(text) || cleanText(values['伤害来源分类']).includes('极轨')) return '极轨终结';
  if (/(?:^|_)Skill\d*(?:_|$)/i.test(text) || cleanText(values['伤害来源分类']).includes('变轨')) return '变轨技能';
  if (/Melee|AirAttack|PerfectEvadeAttack/i.test(text) || cleanText(values['伤害来源分类']).includes('普通攻击')) return '普通攻击';
  if (/Reaction/i.test(text) || cleanText(values['伤害来源分类']).includes('环合')) return '环合反应';
  return cleanText(values['伤害来源分类']) || '未分类';
}

function eventFamily(values) {
  const text = [values.AbilityKey, values.GEName].map(cleanText).join(' ');
  if (/\bLTE\b|_LTE(?:_|$)/i.test(text)) return 'lte';
  if (/\bQTE\b|_QTE(?:_|$)/i.test(text)) return 'qte';
  if (/UltraSkill/i.test(text)) return 'ultra';
  if (/(?:^|_)Skill\d*(?:_|$)/i.test(text)) return 'skill';
  if (/Melee|AirAttack|PerfectEvadeAttack/i.test(text)) return 'melee';
  if (/Reaction/i.test(text)) return 'reaction';
  return 'unknown';
}

function ownRepeatCount(formula, index) {
  if (!formula || formula === '-') return 1;
  const damageExpression = formula.split(',')[0].trim();
  const escaped = String(index).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = damageExpression.match(new RegExp(`\\{${escaped}\\}%\\s*\\*\\s*(\\d+)`));
  return match ? Math.max(1, Number(match[1])) : 1;
}

const groupIds = new Map();
function formulaGroup(values) {
  const key = [values['角色'], values.AbilityKey, values['技能名称'], values['描述'], values['倍率呈现方式']]
    .map(cleanText).join('|');
  if (!groupIds.has(key)) groupIds.set(key, `formula-${groupIds.size + 1}`);
  return groupIds.get(key);
}

const levelHeaders = Array.from({ length: 13 }, (_, index) => `${index + 1}级倍率`);
const segments = recordsFrom(skillRows).map(({ sourceRow, values }) => {
  const characterName = cleanText(values['角色']);
  const characterMatches = charactersByName.get(characterName) || [];
  const displayFormula = cleanText(values['倍率呈现方式']);
  const index = Number.isFinite(Number(values['索引'])) ? Number(values['索引']) : null;
  const multipliers = levelHeaders.map((header) => {
    const value = Number(values[header]);
    return Number.isFinite(value) ? value : null;
  });
  return {
    sourceRow,
    character: characterName,
    characterIds: characterMatches.map((character) => character.id),
    codename: characterMatches[0]?.codename || '',
    abilityKey: cleanText(values.AbilityKey),
    skillName: cleanText(values['技能名称']),
    geName: cleanText(values.GEName),
    sourceCategory: cleanText(values['伤害来源分类']),
    category: normalizeCategory(values),
    family: eventFamily(values),
    damageAttribute: cleanText(values['伤害属性']),
    multiplierType: cleanText(values['倍率类型']),
    description: cleanText(values['描述']),
    formulaGroup: formulaGroup(values),
    index,
    displayFormula,
    damageExpression: displayFormula.split(',')[0].trim(),
    repeatCount: ownRepeatCount(displayFormula, index),
    fixedCritRate: Number(values['固定暴击率']) || 0,
    levelMultipliers: multipliers,
    computable: Boolean(cleanText(values.GEName)) && multipliers.some((value) => value !== null),
  };
});

const geCounts = new Map();
segments.forEach((segment) => {
  const key = segment.geName.toLowerCase();
  if (!key) return;
  geCounts.set(key, (geCounts.get(key) || 0) + 1);
});

const database = {
  schemaVersion: 1,
  source: {
    workbook: '角色属性.xlsx',
    sheet: '角色技能数值',
    sha256: createHash('sha256').update(sourceBytes).digest('hex'),
  },
  stats: {
    characters: characters.length,
    segments: segments.length,
    exactGeNames: geCounts.size,
    duplicateGeNames: [...geCounts.values()].filter((count) => count > 1).length,
  },
  characters,
  segments,
};

await mkdir(dirname(outputPath), { recursive: true });
await writeFile(outputPath, `${JSON.stringify(database)}\n`, 'utf8');
console.log(`Skill database: ${segments.length} segments -> ${outputPath}`);
