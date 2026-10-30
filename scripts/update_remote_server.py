import paramiko
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding='utf-8')

PRIV_KEY = Path.home() / ".ssh" / "id_ed25519"
SSH_HOST = "srv75.mikr.us"
SSH_PORT = 10120
SSH_USER = "root"

print(f"Connecting to {SSH_USER}@{SSH_HOST}:{SSH_PORT}...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
k = paramiko.Ed25519Key.from_private_key_file(str(PRIV_KEY))
client.connect(hostname=SSH_HOST, port=SSH_PORT, username=SSH_USER, pkey=k, timeout=10)
print("Connected successfully!")

def run_cmd(cmd):
    print(f"\n[REMOTE] {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    if out:
        print(f"OUT: {out}")
    if err:
        print(f"ERR: {err}")
    if code != 0:
        print(f"EXIT CODE: {code}")
    return out

# 1. Git pull
run_cmd("cd /opt/nesta-deal-hunter && git pull origin main")

# 2. Run purge script on remote database
run_cmd("cd /opt/nesta-deal-hunter && venv/bin/python scripts/purge_bogus_listings.py")

# 3. Restart service
run_cmd("systemctl restart deal-hunter.service")

# 4. Check status
run_cmd("systemctl status deal-hunter.service --no-pager")

# 5. Check curl
run_cmd("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:40120/")

client.close()
print("\nRemote deployment and purge complete!")
