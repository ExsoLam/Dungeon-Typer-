// Prints one line per PR event from the webhook relay, as it happens.
// Token: DT_RELAY_TOKEN, or ~/.config/dungeon-typer/relay-token (never commit it).
// Remembers the last event in ~/.config/dungeon-typer/relay-seq, so a restart replays
// anything missed (the relay keeps the last 500). Reconnects on its own.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { homedir } from 'node:os';
const dir = process.env.DT_RELAY_DIR || homedir() + '/.config/dungeon-typer';
const base = process.env.DT_RELAY_URL || 'wss://pr-events.dtyper.workers.dev';
const read = f => { try { return readFileSync(dir + '/' + f, 'utf8').trim(); } catch { return ''; } };
const token = process.env.DT_RELAY_TOKEN || read('relay-token');
if (!token) { console.error('No relay token: set DT_RELAY_TOKEN or write ' + dir + '/relay-token'); process.exit(2); }
let seq = parseInt(read('relay-seq') || '0', 10) || 0;
mkdirSync(dir, { recursive: true });

export function line(e) {
  const who = e.actor ? ' by ' + e.actor : '';
  const pr = e.pr ? '#' + e.pr + ' ' : e.branch ? `(${e.branch}) ` : '';
  const what = { pull_request: e.action, pull_request_review: 'review', pull_request_review_comment: 'review comment', issue_comment: 'comment', workflow_run: 'check', ping: 'ping' }[e.event] || e.event;
  return `${pr}${what}${who}${e.detail ? ': ' + e.detail : ''}${e.event === 'pull_request' && e.title ? ': ' + e.title : ''}`;
}

function connect(delay = 1000) {
  const ws = new WebSocket(`${base}/stream?since=${seq}&token=${encodeURIComponent(token)}`);
  let ping;
  ws.onopen = () => { delay = 1000; ping = setInterval(() => ws.send('ping'), 50000); };
  ws.onmessage = m => {
    if (m.data === 'pong') return;
    const e = JSON.parse(m.data);
    if (e.seq <= seq) return;
    seq = e.seq; writeFileSync(dir + '/relay-seq', String(seq));
    console.log(line(e));
  };
  ws.onclose = ev => {
    clearInterval(ping);
    if (ev.code === 1008 || ev.code === 4001) { console.error('Relay refused the token.'); process.exit(1); }
    setTimeout(() => connect(Math.min(delay * 2, 60000)), delay);
  };
  ws.onerror = () => {};
}
async function start() {
  // A WebSocket refusal carries no status, so check the token over HTTP first.
  const res = await fetch(`${base.replace(/^ws/, 'http')}/events?since=${seq}`, { headers: { Authorization: 'Bearer ' + token } }).catch(() => null);
  if (res?.status === 401) { console.error('Relay refused the token.'); process.exit(1); }
  connect();
}
if (import.meta.url === `file://${process.argv[1]}`) start();
