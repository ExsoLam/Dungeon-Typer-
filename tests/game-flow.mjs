import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
// Execute embedded data in memory only. Never write or print word lists.
// The whole script runs: the browser glue is skipped without `window`, and pos()/stagePos() live with the renderer.
const script = readFileSync('typing_dungeon_v48.html', 'utf8').match(/<script>([\s\S]*)<\/script>/)[1];
for (const mode of ['strict', 'original']) {
  const context = vm.createContext({ Math, console, setTimeout });
  vm.runInContext(script + `
    setMode('${mode}'); key('Enter');
    let ticks=0, picker=0;
    while (G.state!=='final' && ticks++<60000) {
      if (G.state==='weapon') { picker++; setWeapon(picker); key('Enter'); continue; }
      if (G.state==='results' || G.state==='over') { key('Enter'); continue; }
      update(0.05);
      const e=G.lock || G.enemies.find(e=>!(e.stagger>0) && !(e.gray>0));
      if (e && G.state==='play') key(CFG.CASE ? e.word[e.idx] : e.word[e.idx].toLowerCase());
    }
    globalThis.out={state:G.state, stages:G.results.length, total:G.final?.total, picker, weapon:G.weapon, names:G.results.map(r=>r.name)};
  `, context);
  assert.equal(context.out.state, 'final');
  assert.equal(context.out.stages, 5);
  assert.equal(context.out.picker, 1, 'the weapon picker opens once in a full run, before stage 3');
  assert.ok(context.out.total > 0);
  console.log(mode + ': full five-stage engine run passed (' + context.out.names.join(', ') + '), total ' + context.out.total + ', weapon ' + context.out.weapon);
}
// a single-stage run opens the picker first
{
  const context = vm.createContext({ Math, console, setTimeout });
  vm.runInContext(script + `setLevel(1); key('Enter'); globalThis.out = { state: G.state }; key('Enter'); globalThis.out.after = G.state + ':' + G.seg;`, context);
  assert.equal(context.out.state, 'weapon'); assert.equal(context.out.after, 'play:1');
  console.log('single-stage run opens the weapon picker first');
}
