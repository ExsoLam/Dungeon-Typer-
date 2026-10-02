import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
// Execute embedded data in memory only. Never write or print word lists.
const script = readFileSync('typing_dungeon_v21.html', 'utf8').match(/<script>([\s\S]*)<\/script>/)[1];
const engine = script.slice(0, script.indexOf('/* ---- canvas renderer:'));
for (const mode of ['strict', 'original']) {
  const context = vm.createContext({ Math, console });
  vm.runInContext(engine + `
    setMode('${mode}'); key('Enter');
    let ticks=0;
    while (G.state!=='final' && ticks++<30000) {
      if (G.state==='results' || G.state==='over') { key('Enter'); continue; }
      update(0.05);
      const e=G.lock || G.enemies.find(e=>!(e.stagger>0));
      if (e && G.state==='play') key(CFG.CASE ? e.word[e.idx] : e.word[e.idx].toLowerCase());
    }
    globalThis.out={state:G.state, stages:G.results.length,total:G.final?.total,lives:G.lives};
  `, context);
  assert.equal(context.out.state, 'final');
  assert.equal(context.out.stages, 3);
  assert.ok(context.out.total > 0);
  console.log(mode + ': full three-stage engine run passed');
}
