import sqlite3
from pathlib import Path
c = sqlite3.connect(':memory:')
for m in sorted(Path('server/migrations').glob('*.sql')): c.executescript(m.read_text())
for scope in ('production','pr-11','pr-12'):
    c.execute('INSERT INTO players(scope,token_hash,name) VALUES(?,?,?)',(scope,'alice','Alice'))
for scope,score in [('production',100),('pr-11',900),('pr-12',500)]:
    c.execute('INSERT INTO runs(scope,id,player_hash,mode,version,score,accuracy,wpm) VALUES(?,?,?,?,?,?,?,?)',(scope,'same-id','alice','strict','v48-2',score,99,60))
assert c.execute("SELECT MAX(score) FROM runs WHERE scope='production'").fetchone()[0] == 100
assert c.execute("SELECT MAX(score) FROM runs WHERE scope='pr-11'").fetchone()[0] == 900
try:
    c.execute("INSERT INTO runs SELECT * FROM runs WHERE scope='production'")
    raise AssertionError('Duplicate accepted')
except sqlite3.IntegrityError:
    pass
# a run inserted without stage or weapon (as every pre-0002 row) is a full pistol run
assert c.execute("SELECT stage, weapon FROM runs WHERE scope='production'").fetchone() == ('all', 'pistol')
c.execute("INSERT INTO runs(scope,id,player_hash,mode,version,stage,weapon,score,accuracy,wpm) VALUES('production','gate-1','alice','strict','v48-2','gate','ray',4321,99,60)")
best = lambda stage: c.execute("SELECT MAX(score) FROM runs WHERE scope='production' AND stage=?", (stage,)).fetchone()[0]
assert best('all') == 100 and best('gate') == 4321 and best('crypt') is None
assert c.execute("SELECT MAX(score), weapon FROM runs WHERE scope='production' AND stage='gate'").fetchone() == (4321, 'ray')
print('Database schema, preview isolation, per-stage boards and duplicate constraints passed')
