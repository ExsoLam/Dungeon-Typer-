"""Generate optional D1 import SQL. Never edit the workflow-owned board."""
import json, hashlib, re
from pathlib import Path
quote = lambda s: "NULL" if s is None else "'" + str(s).replace("'", "''") + "'"
data = json.loads(Path('scores.json').read_text())
statements = []
for mode, rows in data['boards'].items():
    if mode not in ('strict','original'): continue
    for row in rows:
        name, score, sid = row['name'], row['score'], row['id']
        if not re.fullmatch(r'[A-Za-z0-9 _.\-]{1,20}',name) or type(score) is not int or not 1<=score<=1000000:
            raise ValueError('Invalid legacy entry')
        # One historical identity per submission; never claim browser ownership by name.
        player = hashlib.sha256(('legacy:'+sid).encode()).hexdigest()
        statements.append('INSERT OR IGNORE INTO players(scope,token_hash,name) VALUES('+','.join(map(quote,('production',player,name)))+');')
        fields = ('production','legacy:'+sid,player,mode,'v21-1',score,None,None,row['date'])
        statements.append('INSERT OR IGNORE INTO runs(scope,id,player_hash,mode,version,score,accuracy,wpm,created_at) VALUES('+','.join(map(quote,fields))+');')
Path('.deploy').mkdir(exist_ok=True)
Path('.deploy/legacy.sql').write_text('\n'.join(statements)+'\n')
print('Generated .deploy/legacy.sql. Review before applying to production; no database changed.')
