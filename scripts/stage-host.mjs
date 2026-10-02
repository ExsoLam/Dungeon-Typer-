import { mkdirSync, copyFileSync, cpSync, writeFileSync, rmSync } from 'node:fs';
import { resolve } from 'node:path';
const scope = process.env.SCORE_SCOPE || 'local';
const db = process.env.D1_DATABASE_ID || '00000000-0000-0000-0000-000000000000';
if (!/^(local|production|pr-[0-9]+)$/.test(scope)) throw new Error('Invalid score scope');
if (!/^[a-f0-9-]{36}$/.test(db)) throw new Error('Invalid D1 database ID');
const out = resolve('.deploy');
rmSync(out + '/public', { recursive: true, force: true });
mkdirSync(out + '/public', { recursive: true });
copyFileSync('typing_dungeon_v21.html', out + '/public/typing_dungeon_v21.html');
cpSync('SOUNDS', out + '/public/SOUNDS', { recursive: true });
copyFileSync('typing_dungeon_v21.html', out + '/public/index.html');
writeFileSync(out + '/wrangler.json', JSON.stringify({
  name: scope.startsWith('pr-') ? scope : 'play',
  main: '../server/worker.mjs', compatibility_date: '2026-10-01', workers_dev: true,
  assets: { directory: './public', binding: 'ASSETS', run_worker_first: ['/api/*'] },
  vars: { SCORE_SCOPE: scope, REVISION: process.env.REVISION || 'local' },
  d1_databases: [{ binding: 'DB', database_name: scope === 'production' ? 'dungeon-typer-production' : 'dungeon-typer-preview', database_id: db, migrations_dir: '../server/migrations' }]
}, null, 2));
console.log('Staged game for ' + scope);
