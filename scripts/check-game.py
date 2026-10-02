from pathlib import Path
import re, subprocess, tempfile
src = Path('typing_dungeon_v21.html').read_text()
with tempfile.NamedTemporaryFile(suffix='.js', mode='w') as f:
    f.write(re.search(r'<script>(.*)</script>', src, re.S).group(1))
    f.flush()
    subprocess.run(['node', '--check', f.name], check=True)
print('Game JavaScript syntax passed')
