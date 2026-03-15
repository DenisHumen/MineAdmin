import asyncio
import logging
import platform
from typing import Optional

import paramiko

logger = logging.getLogger("mineadmin.ssh")


class SSHSession:
    def __init__(self):
        self.client: Optional[paramiko.SSHClient] = None
        self.channel = None
        self.connected = False

    def connect(self, host: str, port: int, username: str,
                password: str = None, key_path: str = None) -> dict:
        if platform.system() != "Linux":
            return {"success": False, "error": "SSH терминал доступен только на Linux"}

        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": host,
                "port": port,
                "username": username,
                "timeout": 10,
            }

            if key_path:
                try:
                    key = paramiko.RSAKey.from_private_key_file(key_path)
                except Exception:
                    try:
                        key = paramiko.Ed25519Key.from_private_key_file(key_path)
                    except Exception:
                        key = paramiko.ECDSAKey.from_private_key_file(key_path)
                connect_kwargs["pkey"] = key
            elif password:
                connect_kwargs["password"] = password
            else:
                return {"success": False, "error": "Требуется пароль или SSH ключ"}

            self.client.connect(**connect_kwargs)
            self.channel = self.client.invoke_shell(
                term="xterm-256color", width=120, height=40
            )
            self.channel.settimeout(0.1)
            self.connected = True

            return {"success": True}

        except paramiko.AuthenticationException:
            return {"success": False, "error": "Ошибка авторизации: неверные данные"}
        except paramiko.SSHException as e:
            return {"success": False, "error": f"SSH ошибка: {e}"}
        except Exception as e:
            return {"success": False, "error": f"Ошибка подключения: {e}"}

    async def read(self) -> Optional[str]:
        if not self.channel or not self.connected:
            return None
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._do_read)
            return data
        except Exception:
            return None

    def _do_read(self) -> Optional[str]:
        try:
            if self.channel.recv_ready():
                data = self.channel.recv(4096)
                return data.decode("utf-8", errors="replace")
        except Exception:
            pass
        return None

    async def write(self, data: str):
        if not self.channel or not self.connected:
            return
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.channel.send, data.encode())
        except Exception as e:
            logger.error(f"SSH write error: {e}")

    def resize(self, cols: int, rows: int):
        if self.channel and self.connected:
            try:
                self.channel.resize_pty(width=cols, height=rows)
            except Exception:
                pass

    def close(self):
        self.connected = False
        if self.channel:
            try:
                self.channel.close()
            except Exception:
                pass
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass


def test_ssh_connection(host: str, port: int, username: str,
                        password: str = None, key_path: str = None) -> dict:
    session = SSHSession()
    result = session.connect(host, port, username, password, key_path)
    if result["success"]:
        session.close()
        result["message"] = "Подключение успешно"
    return result
