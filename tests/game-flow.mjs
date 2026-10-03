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
// every weapon survives a full run with its perk active
for (const weapon of ['pistol', 'ar', 'ray', 'shotgun', 'xbow']) {
  const context = vm.createContext({ Math, console, setTimeout });
  vm.runInContext(script + `
    key('Enter'); let ticks=0, perks=0; hooks.trim = () => perks++;
    while (G.state!=='final' && ticks++<60000) {
      if (G.state==='weapon') { G.weapon='${weapon}'; key('Enter'); continue; }
      if (G.state==='results' || G.state==='over') { key('Enter'); continue; }
      update(0.05);
      const e=G.lock || G.enemies.find(e=>!(e.stagger>0) && !(e.gray>0));
      if (e && G.state==='play' && e.idx < e.word.length) key(e.word[e.idx]);
    }
    globalThis.out={state:G.state, total:G.final?.total, perks};
  `, context);
  assert.equal(context.out.state, 'final', weapon + ' finishes a full run');
  if (weapon === 'pistol') assert.equal(context.out.perks, 0, 'the pistol has no perk');
  else assert.ok(context.out.perks > 0, weapon + ' perk fires');
  console.log(weapon + ': full run passed, ' + context.out.perks + ' trims, total ' + context.out.total);
}
// targeted perk rules
{
  const context = vm.createContext({ Math, console, setTimeout });
  vm.runInContext(script + `
    const R = {};
    setLevel(0); key('Enter'); key('Enter'); G.queue = []; G.nextSpawn = 1e9; G.enemies = []; G.lock = null;
    const mk = (word, lane) => { const e = spawn('zombie', true); e.word = word; e.lane = lane ?? e.lane; e.born = G.clock - 1; e.hold = 0; e.life = 60; return e; };
    // trim drops a dangling space and finishes a word cut down to what was typed
    let a = mk('ab cd'); trim(a); trim(a); R.space = a.word;
    a.idx = 2; trim(a); R.trimDone = !G.enemies.includes(a);
    // AR: the 4th correct key trims the target
    G.enemies = []; G.lock = null; G.weapon = 'ar'; G.perkN = 0; a = mk('abcdefghij'); 'abcd'.split('').forEach(k => key(k)); R.ar = a.word;
    // ray gun: a hit word burns a letter per quarter second
    G.enemies = []; G.lock = null; G.weapon = 'ray'; G.perkN = 0; a = mk('abcdefghij'); key('a'); for (let i = 0; i < 6; i++) update(0.1); R.ray = a.word;   // update() caps a frame at 0.1 s; 0.6 s burns two letters
    // shotgun: neighbours lose a letter, the target does not
    G.enemies = []; G.lock = null; G.weapon = 'shotgun'; G.perkN = 0; a = mk('abcdefghij'); const b = { ...a, word: 'klmnopqrst', idx: 0, firstT: null }; G.enemies.push(b);   // same spot as the target
    'abcd'.split('').forEach(k => key(k)); R.shotTarget = a.word; R.shotNear = b.word;
    // crossbow: an enemy further back on the same path is hit, the target is not
    G.enemies = []; G.lock = null; G.weapon = 'xbow'; G.perkN = 0; a = mk('abcdefghij'); a.born = G.clock - 40; 
    const f = { ...a, word: 'uvwxyzabcd', idx: 0, firstT: null, born: G.clock - 5 }; G.enemies.push(f);
    'abcd'.split('').forEach(k => key(k)); R.boltTarget = a.word; R.boltBehind = f.word;
    // untyped enemy finished by a perk scores rank E
    G.enemies = []; G.lock = null; let rk = -1; hooks.kill = o => { rk = o.rk; }; const c = mk('z'); trim(c); R.assistRank = rk; R.lastRank = RANKS.length - 1;
    globalThis.out = R;
  `, context);
  const R = context.out;
  assert.equal(R.space, 'ab', 'a dangling space goes with the trimmed letter');
  assert.ok(R.trimDone, 'a word trimmed to the typed part is finished');
  assert.equal(R.ar, 'abcdefghi', 'AR trims one letter on the 4th key');
  assert.equal(R.ray, 'abcdefgh', 'ray gun burns one letter per 0.25 s');
  assert.equal(R.shotTarget, 'abcdefghij', 'shotgun leaves the target alone');
  assert.equal(R.shotNear, 'klmnopqrs', 'shotgun trims an enemy beside the target');
  assert.equal(R.boltTarget, 'abcdefghij', 'crossbow leaves the target alone');
  assert.equal(R.boltBehind, 'uvwxyzabc', 'crossbow bolts trim an enemy behind the target');
  assert.equal(R.assistRank, R.lastRank, 'a perk kill of an untyped enemy is rank E');
  console.log('weapon perk rules passed');
}
