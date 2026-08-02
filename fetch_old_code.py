import paramiko
import sys

hostname = "139.59.39.218"
port = 22
username = "root"
password = "Hlainghninoo001"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(hostname, port, username, password)
    sftp = ssh.open_sftp()
    
    files_to_download = ["messages.py", "bot.py"]
    for f in files_to_download:
        remote_path = f"/root/telegram_bot/{f}"
        local_path = f"old_{f}"
        sftp.get(remote_path, local_path)
        print(f"Downloaded {f} to {local_path}")
        
    sftp.close()
except Exception as e:
    print(f"Error: {e}")
finally:
    ssh.close()
