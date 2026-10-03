import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
// Execute embedded data in memory only. Never write or print word lists.
// The whole script runs: the browser glue is skipped without `window`, and pos()/stagePos() live with the renderer.
const script = readFileSync('typing_dungeon_v48.html', 'utf8').match(/<script>([\s\S]*)<\/script>/)[1];
const PLAY = `
  let ticks=0;
  while (G.state!=='final' && ticks++<60000) {
    if (G.state==='weapon') { picker++; if (pick !== null) setWeapon(pick); key('Enter'); continue; }
    if (G.state==='results' || G.state==='over') { key('Enter'); continue; }
    update(0.05);
    const e=G.lock || G.enemies.find(e=>!(e.stagger>0) && !(e.gray>0));
    if (e && G.state==='play') key(CFG.CASE ? e.word[e.idx] : e.word[e.idx].toLowerCase());
  }`;
for (const mode of ['strict', 'original']) {
  const context = vm.createContext({ Math, console, setTimeout });
  vm.runInContext(script + `
    setMode('${mode}'); G.weapon='xbow'; let picker=0, pick=1; key("Enter"); const startW=G.weapon;` + PLAY + `
    globalThis.out={state:G.state, stages:G.results.length, total:G.final?.total, picker, first:startW, weapon:G.weapon, names:G.results.map(r=>r.name)};
  `, context);
  const o = context.out;
  assert.equal(o.state, 'final'); assert.equal(o.stages, 5); assert.ok(o.total > 0);
  assert.equal(o.first, 'pistol', 'a full run starts with the pistol');
  assert.equal(o.picker, 1, 'the weapon picker opens once in a full run, before stage 3');
  assert.equal(o.weapon, 'ar');
  console.log(mode + ': full five-stage run passed (' + o.names.join(', ') + '), total ' + o.total);
}
// single-stage runs: the picker opens first, and every weapon's effect fires and still lets the stage finish
for (const w of ['pistol', 'ar', 'ray', 'shotgun', 'xbow']) {
  const context = vm.createContext({ Math, console, setTimeout });
  vm.runInContext(script + `
    let trims=0, frees=0; hooks.trim=()=>trims++; const k0=hooks.kill; hooks.kill=o=>{ if (o.free) frees++; };
    setLevel(3); key('Enter'); const st=G.state; let picker=0, pick=null; setWeapon(WEAPONS.findIndex(x=>x.id==='${w}')); key('Enter');` + PLAY + `
    globalThis.out={st, state:G.state, trims, free:frees, total:G.final?.total};
  `, context);
  const o = context.out;
  assert.equal(o.st, 'weapon'); assert.equal(o.state, 'final'); assert.ok(o.total > 0);
  if (w === 'pistol') assert.equal(o.trims, 0); else if (w === 'ar' || w === 'ray') assert.ok(o.trims > 0, w + ' trims letters');
  console.log('single stage with ' + w + ': ' + o.trims + ' letters trimmed, ' + o.free + ' free kills, total ' + o.total);
}
// shotgun and crossbow: two enemies from one zone, the later one just behind; four keys on the front one trim the back one
for (const w of ['shotgun', 'xbow']) {
  const context = vm.createContext({ Math, console, setTimeout });
  vm.runInContext(script + `
    setLevel(3); setWeapon(WEAPONS.findIndex(x=>x.id==='${w}')); newGame(); G.queue=[]; G.enemies=[]; G.nextSpawn=1e9;
    const a=spawn('orc',true); for (let i=0;i<20;i++) update(0.05); const b=spawn('rat',true); b.zone=a.zone; for (let i=0;i<10;i++) update(0.05);
    const len=b.word.length; G.lock=a; for (let i=0;i<4 && G.enemies.includes(a);i++) key(a.word[a.idx]);
    globalThis.out={ before: len, after: b.word.length, ay: pos(a).y, by: pos(b).y };
  `, context);
  const o = context.out;
  assert.ok(o.by < o.ay, 'the second enemy is behind the first');
  assert.equal(o.after, o.before - 1, w + ' trims one letter off the enemy behind');
  console.log(w + ': four keys on the front enemy trimmed the one behind (' + o.before + ' -> ' + o.after + ' letters)');
}
// a trim that empties an untouched enemy's word is a free kill (base points only); on your own target it scores with a rank
{
  const context = vm.createContext({ Math, console, setTimeout });
  vm.runInContext(script + `
    setLevel(3); newGame(); G.queue=[]; G.enemies=[]; G.nextSpawn=1e9;
    const a=spawn('orc',true); a.word=a.word.slice(0,1); const b0=G.st.base, w0=G.st.words; trimWord(a);
    const freeOk = !G.enemies.includes(a) && G.st.base===b0+15 && G.st.words===w0;
    const c=spawn('rat',true); G.lock=c; key(c.word[0]); c.word=c.word.slice(0, c.idx+1); trimWord(c);
    globalThis.out={ freeOk, ownOk: !G.enemies.includes(c) && G.st.words===w0+1 };
  `, context);
  assert.ok(context.out.freeOk, 'free kill scores base only'); assert.ok(context.out.ownOk, 'your own trimmed target scores with a rank');
  console.log('trim kills: free kill on an untouched enemy, ranked kill on your own target');
}
