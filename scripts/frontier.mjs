#!/usr/bin/env node
// Mechanical frontier check; semantic completeness remains the designer's job.
// Exit 0: mechanically closed, 1: more decisions/revisions, 2: invalid record.
import { readFile } from 'node:fs/promises';

const file = process.argv[2] || 'design/decisions.md';
let source;
try { source = await readFile(file, 'utf8'); }
catch (e) { console.error(`cannot read ${file}: ${e.message}`); process.exit(2); }

const decisions = new Map();
const errors = [];
for (const [i, line] of source.split(/\r?\n/).entries()) {
  const match = line.match(/^\s*- \[([ xX])\] (D\d+)(?: \(after: ([^)]+)\))?:\s*(\S.*)$/);
  if (!match) {
    if (/^\s*- \[[ xX]\] D\d+/.test(line)) errors.push(`line ${i + 1}: invalid decision syntax`);
    continue;
  }
  const [, mark, id, deps = '', statement] = match;
  if (decisions.has(id)) { errors.push(`line ${i + 1}: duplicate ${id}`); continue; }
  const after = deps ? deps.split(',').map(s => s.trim()) : [];
  decisions.set(id, { id, done: mark.toLowerCase() === 'x', after, statement });
}
for (const d of decisions.values()) {
  for (const dep of d.after) {
    if (!decisions.has(dep)) errors.push(`${d.id}: unknown dependency ${dep}`);
    if (dep === d.id) errors.push(`${d.id}: self-dependency`);
  }
}
const visiting = new Set(), visited = new Set();
function visit(id) {
  if (visiting.has(id)) { errors.push(`cycle through ${id}`); return; }
  if (visited.has(id)) return;
  visiting.add(id);
  for (const dep of decisions.get(id).after) if (decisions.has(dep) && dep !== id) visit(dep);
  visiting.delete(id); visited.add(id);
}
for (const id of decisions.keys()) visit(id);
if (errors.length) { for (const e of [...new Set(errors)]) console.error(`invalid: ${e}`); process.exit(2); }

// Effective completion is transitive: reopening D1 also stales D2 -> D3.
const stable = new Map();
function isStable(id) {
  if (stable.has(id)) return stable.get(id);
  const d = decisions.get(id);
  const ok = d.done && d.after.every(isStable);
  stable.set(id, ok);
  return ok;
}
let pending = 0;
for (const d of decisions.values()) {
  const unmet = d.after.filter(id => !isStable(id));
  if (d.done && unmet.length) {
    console.log(`reopen ${d.id}: depends on open ${unmet.join(', ')}`);
    pending++;
  } else if (!d.done && !unmet.length) {
    console.log(`ready ${d.id}: ${d.statement}`);
    pending++;
  } else if (!d.done) {
    console.log(`waiting ${d.id}: after ${unmet.join(', ')}`);
    pending++;
  }
}
if (pending) {
  console.log(`${pending} unresolved or stale; decide ready questions, then rerun`);
  process.exit(1);
}
console.log(`mechanically closed (${decisions.size} decisions); perform semantic two-implementer challenge`);
