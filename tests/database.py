import sqlite3
from pathlib import Path
c = sqlite3.connect(':memory:')
c.executescript(Path('server/migrations/0001_scores.sql').read_text())
for scope in ('production','pr-11','pr-12'):
    c.execute('INSERT INTO players(scope,token_hash,name) VALUES(?,?,?)',(scope,'alice','Alice'))
for scope,score in [('production',100),('pr-11',900),('pr-12',500)]:
    c.execute('INSERT INTO runs(scope,id,player_hash,mode,version,score,accuracy,wpm) VALUES(?,?,?,?,?,?,?,?)',(scope,'same-id','alice','strict','v21-1',score,99,60))
assert c.execute("SELECT MAX(score) FROM runs WHERE scope='production'").fetchone()[0] == 100
assert c.execute("SELECT MAX(score) FROM runs WHERE scope='pr-11'").fetchone()[0] == 900
try:
    c.execute("INSERT INTO runs SELECT * FROM runs WHERE scope='production'")
    raise AssertionError('Duplicate accepted')
except sqlite3.IntegrityError:
    pass
print('Database schema, preview isolation and duplicate constraints passed')
