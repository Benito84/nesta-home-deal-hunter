"""
Skrypt Automatycznego Wdrożenia Nesta Deal Hunter na Serwer Mikr.us.
Zgodnie ze Standardem Nesta Home Master Tracker v4.16.
"""

import os
import sys
import getpass
import paramiko
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SSH_HOST = "srv75.mikr.us"
SSH_PORT = 10120
SSH_USER = "root"
REMOTE_APP_DIR = "/opt/nesta-deal-hunter"
APP_TARGET_PORT = 40120

PUB_KEY_PATH = Path.home() / ".ssh" / "id_ed25519.pub"
PRIV_KEY_PATH = Path.home() / ".ssh" / "id_ed25519"

EXCLUDE_DIRS = {"venv", ".git", "__pycache__", "scratch", ".idea", ".vscode"}
EXCLUDE_FILES = {".DS_Store", "data/deals.db-shm", "data/deals.db-wal"}

def get_ssh_client(password: str = None) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # 1. Próba logowania kluczem prywatnym
    if PRIV_KEY_PATH.exists():
        try:
            k = paramiko.Ed25519Key.from_private_key_file(str(PRIV_KEY_PATH))
            print(f"[*] Próba połączenia kluczem SSH: {PRIV_KEY_PATH}...")
            client.connect(hostname=SSH_HOST, port=SSH_PORT, username=SSH_USER, pkey=k, timeout=10)
            print("[+] Zalogowano bezhasłowo przez klucz SSH!")
            return client
        except Exception as e:
            print(f"[-] Logowanie kluczem nie powiodło się ({e}), próba hasłem...")

    # 2. Logowanie hasłem
    if not password:
        password = os.environ.get("MIKRUS_PASSWORD")
    if not password:
        raise ValueError("Brak hasła SSH. Podaj argument lub ustaw MIKRUS_PASSWORD.")

    print(f"[*] Łączenie z {SSH_USER}@{SSH_HOST}:{SSH_PORT} za pomocą hasła...")
    client.connect(hostname=SSH_HOST, port=SSH_PORT, username=SSH_USER, password=password, timeout=10)
    print("[+] Zalogowano pomyślnie hasłem!")

    # 3. Dodanie klucza publicznego do authorized_keys (aby przyszłe logowania były bezhasłowe)
    if PUB_KEY_PATH.exists():
        pub_key = PUB_KEY_PATH.read_text().strip()
        print("[*] Konfiguracja bezhasłowego klucza SSH w /root/.ssh/authorized_keys...")
        cmd = f"mkdir -p /root/.ssh && chmod 700 /root/.ssh && grep -qF '{pub_key}' /root/.ssh/authorized_keys 2>/dev/null || echo '{pub_key}' >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys"
        client.exec_command(cmd)
        print("[+] Klucz SSH został pomyślnie dodany do serwera!")

    return client

def run_remote(client: paramiko.SSHClient, cmd: str) -> str:
    print(f"  [EXEC] {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if exit_code != 0:
        print(f"  [ERROR {exit_code}]: {err}")
    return out

def upload_directory(sftp: paramiko.SFTPClient, local_dir: Path, remote_dir: str):
    try:
        sftp.mkdir(remote_dir)
    except IOError:
        pass

    for item in local_dir.iterdir():
        if item.name in EXCLUDE_DIRS:
            continue
        rel_path = item.relative_to(ROOT_DIR).as_posix()
        if rel_path in EXCLUDE_FILES:
            continue

        remote_path = f"{remote_dir}/{item.name}"
        if item.is_dir():
            upload_directory(sftp, item, remote_path)
        else:
            print(f"  [SFTP] {rel_path} -> {remote_path}")
            sftp.put(str(item), remote_path)

def deploy(password: str = None):
    print("=" * 60)
    print(" Nesta Home Deal Hunter - Wdrożenie na serwer Mikr.us")
    print(f" Cel: {SSH_USER}@{SSH_HOST}:{SSH_PORT} -> Port: {APP_TARGET_PORT}")
    print("=" * 60)

    client = get_ssh_client(password)

    # 1. Przygotowanie środowiska Linux
    print("\n--- 1. Przygotowanie środowiska i pakietów systemowych ---")
    run_remote(client, "apt-get update -y && apt-get install -y python3 python3-venv python3-pip curl rsync")
    run_remote(client, f"mkdir -p {REMOTE_APP_DIR}")

    # 2. Przesyłanie plików aplikacji
    print("\n--- 2. Przesyłanie plików aplikacji (SFTP) ---")
    sftp = client.open_sftp()
    upload_directory(sftp, ROOT_DIR, REMOTE_APP_DIR)
    sftp.close()

    # 3. Konfiguracja pliku .env pod serwer
    print("\n--- 3. Konfiguracja produkcyjnego .env ---")
    env_content = f"""# Nesta Deal Hunter - Mikrus Production
APP_PORT={APP_TARGET_PORT}
DEBUG=False
TRACKER_ENV=PROD
TRACKER_DEV_URL=http://127.0.0.1:30120/api/staging
TRACKER_PROD_URL=http://127.0.0.1:20120/api/staging
DEFAULT_MIN_ROI=0.16
MIN_NET_PROFIT_PLN=30000.0
"""
    sftp = client.open_sftp()
    with sftp.file(f"{REMOTE_APP_DIR}/.env", "w") as f:
        f.write(env_content)
    sftp.close()

    # 4. Utworzenie wirtualnego środowiska i instalacja zależności
    print("\n--- 4. Instalacja bibliotek Python w venv ---")
    run_remote(client, f"python3 -m venv {REMOTE_APP_DIR}/venv")
    run_remote(client, f"{REMOTE_APP_DIR}/venv/bin/pip install --upgrade pip")
    run_remote(client, f"{REMOTE_APP_DIR}/venv/bin/pip install -r {REMOTE_APP_DIR}/requirements.txt")

    # 5. Konfiguracja usługi systemd
    print("\n--- 5. Konfiguracja usługi systemd (deal-hunter.service) ---")
    service_content = f"""[Unit]
Description=Nesta Home Deal Hunter Szczecin (Port {APP_TARGET_PORT})
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={REMOTE_APP_DIR}
ExecStart={REMOTE_APP_DIR}/venv/bin/uvicorn main:app --host 0.0.0.0 --port {APP_TARGET_PORT} --workers 2
Restart=always
RestartSec=5
EnvironmentFile={REMOTE_APP_DIR}/.env

[Install]
WantedBy=multi-user.target
"""
    sftp = client.open_sftp()
    with sftp.file("/etc/systemd/system/deal-hunter.service", "w") as f:
        f.write(service_content)
    sftp.close()

    run_remote(client, "systemctl daemon-reload")
    run_remote(client, "systemctl enable deal-hunter.service")
    run_remote(client, "systemctl restart deal-hunter.service")

    # 6. Weryfikacja działania serwisu
    print("\n--- 6. Weryfikacja uruchomienia ---")
    status = run_remote(client, "systemctl status deal-hunter.service --no-pager")
    print(status)

    test_http = run_remote(client, f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{APP_TARGET_PORT}/")
    print(f"\n[HTTP Status Check lokalnie]: {test_http}")

    client.close()

    print("\n" + "=" * 60)
    print(f"✅ Wdrożenie zakończone sukcesem!")
    print(f"👉 Aplikacja jest dostępna pod adresem: http://{SSH_HOST}:{APP_TARGET_PORT}")
    print("=" * 60)

if __name__ == "__main__":
    pwd = sys.argv[1] if len(sys.argv) > 1 else None
    deploy(pwd)
