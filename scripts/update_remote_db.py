import sys
sys.stdout.reconfigure(encoding='utf-8')
import paramiko
from pathlib import Path

k = paramiko.Ed25519Key.from_private_key_file(str(Path.home() / '.ssh' / 'id_ed25519'))
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('srv75.mikr.us', port=10120, username='root', pkey=k)

update_py = """import sqlite3
conn = sqlite3.connect('/opt/nesta-deal-hunter/data/deals.db')
c = conn.cursor()
c.execute("UPDATE listings SET gate_1_decision = ? WHERE gate_1_decision = ?", ('DO POCZEKALNI', 'DZWONIMY'))
print('Remote DB updated rows:', c.rowcount)
conn.commit()
conn.close()
"""

sftp = c.open_sftp()
with sftp.file('/tmp/update_db.py', 'w') as f:
    f.write(update_py)
sftp.close()

_, stdout, _ = c.exec_command('python3 /tmp/update_db.py && rm -f /tmp/update_db.py')
print(stdout.read().decode())

c.close()
