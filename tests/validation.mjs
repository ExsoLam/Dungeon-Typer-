import assert from 'node:assert/strict';
import { validateRun } from '../server/worker.mjs';
const run = { id: '12345678-1234-4234-8234-123456789012', mode: 'strict', version: 'v48-2', stage: 'all', weapon: 'pistol', score: 1234, accuracy: 98, wpm: 70 };
assert.equal(validateRun(run), true);
for (const patch of [{ mode: 'normal' }, { score: 0 }, { score: 1.5 }, { score: 1000001 }, { accuracy: 101 }, { wpm: -1 }, { version: 'future' }, { version: 'v48-1' }, { id: 'bad' }, { stage: 'nowhere' }, { stage: undefined }, { weapon: 'bazooka' }, { weapon: undefined }]) assert.equal(validateRun({ ...run, ...patch }), false);
assert.equal(validateRun({ ...run, mode: 'original' }), true);
for (const stage of ['corridor', 'control', 'gate', 'courtyard', 'crypt']) assert.equal(validateRun({ ...run, stage }), true);
for (const weapon of ['ar', 'ray', 'shotgun', 'xbow']) assert.equal(validateRun({ ...run, weapon }), true);
console.log('Score validation passed');
