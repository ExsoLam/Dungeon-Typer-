// GitHub webhook relay. GitHub POSTs signed PR events to /github; agents listen on
// /stream (WebSocket) or poll /events. One Durable Object holds the listeners and
// the last 500 events, so a listener that reconnects with ?since=<seq> misses nothing.
const KEEP = 500;
const json = (body, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'no-store' } });
const enc = new TextEncoder();
const hex = buf => [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
const clip = (s, n = 300) => (s || '').replace(/\s+/g, ' ').trim().slice(0, n);

export function sameString(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function verifySignature(secret, raw, header) {
  if (!secret || !header?.startsWith('sha256=')) return false;
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return sameString('sha256=' + hex(await crypto.subtle.sign('HMAC', key, enc.encode(raw))), header);
}

// One compact line of truth per event, or null for events agents do not need.
export function summarise(event, p) {
  const base = { event, action: p.action || '', actor: p.sender?.login || '', repo: p.repository?.full_name || '' };
  switch (event) {
    case 'ping': return { ...base, detail: 'webhook connected: ' + clip(p.zen, 120) };
    case 'pull_request': {
      const pr = p.pull_request;
      const action = p.action === 'closed' && pr.merged ? 'merged' : p.action;
      return { ...base, action, pr: pr.number, title: pr.title, head: pr.head?.sha?.slice(0, 7), url: pr.html_url };
    }
    case 'pull_request_review':
      if (p.action !== 'submitted' && p.action !== 'dismissed') return null;
      return { ...base, pr: p.pull_request.number, title: p.pull_request.title, detail: (p.review.state || '').toLowerCase() + (p.review.body ? ': ' + clip(p.review.body) : ''), url: p.review.html_url };
    case 'pull_request_review_comment':
      if (p.action !== 'created') return null;
      return { ...base, pr: p.pull_request.number, title: p.pull_request.title, detail: (p.comment.path ? p.comment.path + ': ' : '') + clip(p.comment.body), url: p.comment.html_url };
    case 'issue_comment':
      if (p.action !== 'created' || !p.issue?.pull_request) return null;
      return { ...base, pr: p.issue.number, title: p.issue.title, detail: clip(p.comment.body), url: p.comment.html_url };
    case 'workflow_run': {
      if (p.action !== 'completed') return null;
      const run = p.workflow_run;
      return { ...base, pr: run.pull_requests?.[0]?.number, detail: `${run.name}: ${run.conclusion}`, branch: run.head_branch, head: run.head_sha?.slice(0, 7), url: run.html_url };
    }
    default: return null;
  }
}

export class Hub {
  constructor(state) {
    this.state = state;
    if (typeof WebSocketRequestResponsePair !== 'undefined') state.setWebSocketAutoResponse(new WebSocketRequestResponsePair('ping', 'pong'));
  }
  async since(seq) {
    const rows = await this.state.storage.list({ prefix: 'e:', start: 'e:' + String(seq + 1).padStart(12, '0') });
    return [...rows.values()];
  }
  async fetch(request) {
    const url = new URL(request.url);
    const since = Math.max(0, parseInt(url.searchParams.get('since') || '0', 10) || 0);
    if (url.pathname === '/publish') {
      const seq = ((await this.state.storage.get('seq')) || 0) + 1;
      const event = { seq, at: new Date().toISOString(), ...(await request.json()) };
      await this.state.storage.put({ seq, ['e:' + String(seq).padStart(12, '0')]: event });
      if (seq > KEEP) await this.state.storage.delete('e:' + String(seq - KEEP).padStart(12, '0'));
      const line = JSON.stringify(event);
      for (const ws of this.state.getWebSockets()) { try { ws.send(line); } catch {} }
      return json({ seq });
    }
    if (url.pathname === '/events') return json({ events: await this.since(since) });
    if (url.pathname === '/stream') {
      const [client, server] = Object.values(new WebSocketPair());
      this.state.acceptWebSocket(server);
      for (const event of await this.since(since)) server.send(JSON.stringify(event));
      return new Response(null, { status: 101, webSocket: client });
    }
    return json({ error: 'Not found.' }, 404);
  }
  webSocketMessage() {}
  webSocketClose(ws, code) { try { ws.close(code); } catch {} }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const configured = Boolean(env.GITHUB_WEBHOOK_SECRET && env.LISTEN_TOKEN);
    if (url.pathname === '/health') return json({ ok: true, configured });
    if (!configured) return json({ error: 'Relay secrets are not set (see docs/WEBHOOK.md).' }, 503);
    const hub = env.HUB.get(env.HUB.idFromName('main'));
    if (url.pathname === '/github' && request.method === 'POST') {
      const raw = await request.text();
      if (raw.length > 1_000_000) return json({ error: 'Too large.' }, 413);
      if (!(await verifySignature(env.GITHUB_WEBHOOK_SECRET, raw, request.headers.get('X-Hub-Signature-256')))) return json({ error: 'Bad signature.' }, 401);
      let payload;
      try { payload = JSON.parse(raw); } catch { return json({ error: 'Invalid JSON.' }, 400); }
      const event = summarise(request.headers.get('X-GitHub-Event') || '', payload);
      if (!event) return new Response(null, { status: 204 });
      return hub.fetch('https://hub/publish', { method: 'POST', body: JSON.stringify({ delivery: request.headers.get('X-GitHub-Delivery') || '', ...event }) });
    }
    if (url.pathname === '/stream' || url.pathname === '/events') {
      if (!sameString(url.searchParams.get('token') || request.headers.get('Authorization')?.replace(/^Bearer /, '') || '', env.LISTEN_TOKEN)) return json({ error: 'Unauthorised.' }, 401);
      if (url.pathname === '/stream' && request.headers.get('Upgrade') !== 'websocket') return json({ error: 'WebSocket upgrade required.' }, 426);
      return hub.fetch(request);
    }
    return json({ error: 'Not found.' }, 404);
  }
};
