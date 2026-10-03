const VERSION = 'v48-2';
const json = (body, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'no-store' } });
const hash = async value => [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)))].map(b => b.toString(16).padStart(2, '0')).join('');
const tokenPattern = /^[a-f0-9]{64}$/;
export function validateRun(data) {
  return data && /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(data.id) && ['strict', 'original'].includes(data.mode)
    && data.version === VERSION && Number.isInteger(data.score) && data.score >= 1 && data.score <= 1000000
    && Number.isFinite(data.accuracy) && data.accuracy >= 0 && data.accuracy <= 100
    && Number.isFinite(data.wpm) && data.wpm >= 0 && data.wpm <= 1000;
}
async function identity(request) {
  const token = request.headers.get('Authorization')?.replace(/^Bearer /, '');
  return tokenPattern.test(token || '') ? hash(token) : null;
}
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith('/api/')) return env.ASSETS.fetch(request);
    const scope = env.SCORE_SCOPE;
    if (!scope || !env.DB) return json({ error: 'Score service is not configured.' }, 503);
    if (url.pathname === '/api/health') return json({ version: VERSION, scope, revision: env.REVISION });
    try {
      if (request.method === 'GET' && url.pathname === '/api/leaderboard') {
        const mode = url.searchParams.get('mode') || 'strict';
        if (!['strict', 'original'].includes(mode)) return json({ error: 'Unknown mode.' }, 400);
        const rows = await env.DB.prepare(`SELECT p.name, MAX(r.score) AS score FROM runs r
          JOIN players p ON p.scope=r.scope AND p.token_hash=r.player_hash
          WHERE r.scope=? AND r.mode=? AND r.version=? GROUP BY r.player_hash
          ORDER BY score DESC, p.created_at ASC, r.player_hash ASC LIMIT 100`).bind(scope, mode, VERSION).all();
        const player = await identity(request);
        const best = player ? await env.DB.prepare('SELECT MAX(score) AS best FROM runs WHERE scope=? AND player_hash=? AND mode=? AND version=?').bind(scope, player, mode, VERSION).first() : null;
        return json({ mode, version: VERSION, board: rows.results, best: best?.best || 0 });
      }
      if (request.method !== 'POST') return json({ error: 'Not found.' }, 404);
      if (request.headers.get('Origin') !== url.origin) return json({ error: 'Same-origin requests required.' }, 403);
      if (!request.headers.get('Content-Type')?.startsWith('application/json')) return json({ error: 'JSON required.' }, 415);
      const raw = await request.text();
      if (raw.length > 2048) return json({ error: 'Request too large.' }, 413);
      let data;
      try { data = JSON.parse(raw); } catch { return json({ error: 'Invalid JSON.' }, 400); }
      if (url.pathname === '/api/player') {
        const name = typeof data.name === 'string' ? data.name.trim().replace(/\s+/g, ' ') : '';
        if (!/^[A-Za-z0-9 _.\-]{1,20}$/.test(name)) return json({ error: 'Use 1 to 20 letters, numbers, spaces, _ . or -.' }, 400);
        const existing = await identity(request);
        if (existing) {
          const player = await env.DB.prepare('SELECT name FROM players WHERE scope=? AND token_hash=?').bind(scope, existing).first();
          if (!player) return json({ error: 'Player not found. Reset this browser identity.' }, 401);
          await env.DB.prepare('UPDATE players SET name=? WHERE scope=? AND token_hash=?').bind(name, scope, existing).run();
          return json({ name });
        }
        const token = [...crypto.getRandomValues(new Uint8Array(32))].map(b => b.toString(16).padStart(2, '0')).join('');
        await env.DB.prepare('INSERT INTO players(scope,token_hash,name) VALUES(?,?,?)').bind(scope, await hash(token), name).run();
        return json({ name, token }, 201);
      }
      if (url.pathname !== '/api/scores') return json({ error: 'Not found.' }, 404);
      const player = await identity(request);
      if (!player) return json({ error: 'Choose a player name first.' }, 401);
      if (!validateRun(data)) return json({ error: 'Invalid score submission.' }, 400);
      const known = await env.DB.prepare('SELECT name FROM players WHERE scope=? AND token_hash=?').bind(scope, player).first();
      if (!known) return json({ error: 'Player not found.' }, 401);
      const previous = await env.DB.prepare('SELECT player_hash,mode,version,score,accuracy,wpm FROM runs WHERE scope=? AND id=?').bind(scope, data.id).first();
      if (previous && (previous.player_hash !== player || ['mode', 'version', 'score', 'accuracy', 'wpm'].some(k => previous[k] !== data[k]))) return json({ error: 'Submission ID already used.' }, 409);
      if (!previous) {
        const recent = await env.DB.prepare("SELECT COUNT(*) AS n FROM runs WHERE scope=? AND player_hash=? AND created_at > strftime('%Y-%m-%dT%H:%M:%fZ','now','-1 minute')").bind(scope, player).first();
        if (recent.n >= 5) return json({ error: 'Too many scores. Retry in a minute.' }, 429);
        await env.DB.prepare('INSERT OR IGNORE INTO runs(scope,id,player_hash,mode,version,score,accuracy,wpm) VALUES(?,?,?,?,?,?,?,?)').bind(scope, data.id, player, data.mode, data.version, data.score, data.accuracy, data.wpm).run();
      }
      // Recheck after INSERT OR IGNORE so simultaneous retries cannot claim another run.
      const stored = await env.DB.prepare('SELECT player_hash,mode,version,score,accuracy,wpm FROM runs WHERE scope=? AND id=?').bind(scope, data.id).first();
      if (stored.player_hash !== player || ['mode','version','score','accuracy','wpm'].some(k => stored[k] !== data[k])) return json({ error: 'Submission ID already used.' }, 409);
      const best = await env.DB.prepare('SELECT MAX(score) AS best FROM runs WHERE scope=? AND player_hash=? AND mode=? AND version=?').bind(scope, player, data.mode, VERSION).first();
      const rank = await env.DB.prepare(`SELECT COUNT(*)+1 AS rank FROM (SELECT player_hash,MAX(score) AS best FROM runs WHERE scope=? AND mode=? AND version=? GROUP BY player_hash) WHERE best>?`).bind(scope, data.mode, VERSION, best.best).first();
      return json({ saved: true, best: best.best, rank: rank.rank });
    } catch (error) {
      console.error('Score service failure', error);
      return json({ error: 'Score service unavailable. Please retry.' }, 503);
    }
  }
};
