// Unit checks for the webhook relay: signatures, event summaries and auth, with a fake Durable Object.
import assert from 'node:assert/strict';
import worker, { verifySignature, summarise, sameString } from '../relay/worker.mjs';

const secret = 'test-secret';
const sign = async raw => {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return 'sha256=' + [...new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(raw)))].map(b => b.toString(16).padStart(2, '0')).join('');
};

const raw = '{"zen":"hi"}';
assert.ok(await verifySignature(secret, raw, await sign(raw)));
assert.ok(!(await verifySignature(secret, raw + ' ', await sign(raw))));
assert.ok(!(await verifySignature(secret, raw, 'sha1=abc')));
assert.ok(!(await verifySignature('', raw, await sign(raw))));
assert.ok(sameString('abc', 'abc') && !sameString('abc', 'abd') && !sameString('abc', 'ab'));

const sender = { login: 'ExsoLam' };
assert.equal(summarise('pull_request', { action: 'closed', sender, pull_request: { number: 7, title: 't', merged: true, head: { sha: 'abcdef123' } } }).action, 'merged');
assert.equal(summarise('pull_request_review', { action: 'submitted', sender, pull_request: { number: 7 }, review: { state: 'APPROVED', body: '' } }).detail, 'approved');
assert.equal(summarise('issue_comment', { action: 'created', sender, issue: { number: 3 }, comment: { body: 'x' } }), null, 'issue comments that are not on PRs are dropped');
assert.equal(summarise('issue_comment', { action: 'created', sender, issue: { number: 3, pull_request: {} }, comment: { body: ' hello\n there ' } }).detail, 'hello there');
assert.equal(summarise('workflow_run', { action: 'requested', workflow_run: {} }), null);
assert.equal(summarise('workflow_run', { action: 'completed', sender, workflow_run: { name: 'PR hygiene', conclusion: 'failure', pull_requests: [{ number: 9 }] } }).detail, 'PR hygiene: failure');
assert.equal(summarise('push', {}), null);

const published = [];
const env = {
  GITHUB_WEBHOOK_SECRET: secret, LISTEN_TOKEN: 'listen',
  HUB: { idFromName: () => 'id', get: () => ({ fetch: async (url, init) => {
    if (typeof url === 'string' && url.endsWith('/publish')) { published.push(JSON.parse(init.body)); return Response.json({ seq: published.length }); }
    return Response.json({ events: published });
  } }) }
};
const post = async (event, body, sig) => worker.fetch(new Request('https://r/github', { method: 'POST', body, headers: { 'X-GitHub-Event': event, 'X-Hub-Signature-256': sig ?? await sign(body) } }), env);

assert.equal((await post('ping', raw, 'sha256=00')).status, 401, 'bad signature refused');
assert.equal((await post('ping', raw)).status, 200);
assert.equal((await post('push', '{}')).status, 204, 'irrelevant events dropped');
assert.equal(published.length, 1);
assert.equal((await worker.fetch(new Request('https://r/events?token=nope'), env)).status, 401);
assert.equal((await worker.fetch(new Request('https://r/events?token=listen'), env)).status, 200);
assert.equal((await worker.fetch(new Request('https://r/stream?token=listen'), env)).status, 426);
assert.equal((await worker.fetch(new Request('https://r/github', { method: 'POST', body: '{}' }), { HUB: env.HUB })).status, 503, 'unconfigured relay refuses');
console.log('relay checks passed');
