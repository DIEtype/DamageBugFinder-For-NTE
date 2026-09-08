import { readFileSync } from 'node:fs';

const database = JSON.parse(readFileSync(new URL('../data/official-skill-segments.json', import.meta.url), 'utf8'));
const segments = database.segments || [];

if (database.schemaVersion !== 1) throw new Error('Unsupported official skill database schema');
if (segments.length < 600) throw new Error(`Official skill database is unexpectedly small: ${segments.length}`);
if (!database.source?.sha256 || database.source.sha256.length !== 64) throw new Error('Missing source workbook hash');
if (!segments.every((segment) => Array.isArray(segment.levelMultipliers) && segment.levelMultipliers.length === 13)) {
  throw new Error('Every skill segment must contain levels 1–13');
}

function uniqueGe(name) {
  const matches = segments.filter((segment) => segment.geName === name);
  if (matches.length !== 1) throw new Error(`${name} should have exactly one database row, found ${matches.length}`);
  return matches[0];
}

const lingkeSkill3 = uniqueGe('GE_Player_Radio072_Skill3_Damage');
if (lingkeSkill3.category !== '变轨技能' || Math.abs(lingkeSkill3.levelMultipliers[12] - 0.599) > 1e-10) {
  throw new Error('Lingke Skill3 mapping regression');
}

const throwXiaozhen = uniqueGe('GE_Player_Radio072_Skill1_ThrowXiaozhen_Damage');
if (throwXiaozhen.category !== '同频合击' || throwXiaozhen.repeatCount !== 3
  || Math.abs(throwXiaozhen.levelMultipliers[12] - 0.839) > 1e-10) {
  throw new Error('ThrowXiaozhen mapping regression');
}

console.log(`Official skill database: OK (${segments.length} segments, ${database.stats?.duplicateGeNames || 0} duplicate GE names)`);
