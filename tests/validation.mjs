import assert from 'node:assert/strict';
import { validateRun } from '../server/worker.mjs';
const run = { id: '12345678-1234-4234-8234-123456789012', mode: 'strict', version: 'v48-1', score: 1234, accuracy: 98, wpm: 70 };
assert.equal(validateRun(run), true);
for (const patch of [{ mode: 'normal' }, { score: 0 }, { score: 1.5 }, { score: 1000001 }, { accuracy: 101 }, { wpm: -1 }, { version: 'future' }, { id: 'bad' }]) assert.equal(validateRun({ ...run, ...patch }), false);
assert.equal(validateRun({ ...run, mode: 'original' }), true);
console.log('Score validation passed');
