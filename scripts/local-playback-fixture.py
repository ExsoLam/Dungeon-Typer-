# Local browser fixture only. Staging removes it before every deployment.
from pathlib import Path
src = Path('typing_dungeon_v48.html').read_text()
fixture = '''<button id="testTarget" style="position:fixed;bottom:40px;left:5px;z-index:9">Test: one keyboard target</button><button id="testWave" style="position:fixed;bottom:5px;left:5px;z-index:9">Test: complete current wave</button><script>
document.getElementById('testTarget').onclick=()=>{ newGame(); spawn('rat'); G.enemies=G.enemies.slice(0,1); Object.assign(G.enemies[0],{word:'Test',value:20,life:10000}); G.queue=[]; G.nextSpawn=10000; };
document.getElementById('testWave').onclick=()=>{
  let ticks=0;
  while(G.state==='play' && ticks++<20000){
    update(0.05);
    const e=G.lock || G.enemies.find(e=>!(e.stagger>0) && !(e.gray>0));
    if(e && G.state==='play') key(CFG.CASE?e.word[e.idx]:e.word[e.idx].toLowerCase());
  }
};
</script>'''
Path('.deploy/public/playback-test.html').write_text(src.replace('</body>', fixture+'</body>', 1))
print('Local test fixture created. Do not publish it; staging removes it.')
