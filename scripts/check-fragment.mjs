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

console.log('Fragment JavaScript syntax: OK');
