import paramiko
import sys
import os

hostname = "139.59.39.218"
port = 22
username = "root"
password = "Hlainghninoo001"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print("Connecting to SSH...")
    ssh.connect(hostname, port, username, password)
    
    # Run ls in /root/telegram_bot
    stdin, stdout, stderr = ssh.exec_command("ls -la /root/telegram_bot")
    print("Files in /root/telegram_bot:")
    print(stdout.read().decode())
    
    # Read .env
    stdin, stdout, stderr = ssh.exec_command("cat /root/telegram_bot/.env")
    env_content = stdout.read().decode()
    if env_content:
        print(".env found on server:")
        print(env_content)
    else:
        print("No .env found or empty.")
    
    # SFTP bot_data.db
    print("Starting SFTP to download bot_data.db...")
    sftp = ssh.open_sftp()
    remote_path = "/root/telegram_bot/bot_data.db"
    local_path = "bot_data.db"
    sftp.get(remote_path, local_path)
    sftp.close()
    
    print(f"Successfully downloaded {local_path}, size: {os.path.getsize(local_path)} bytes")
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
finally:
    ssh.close()
