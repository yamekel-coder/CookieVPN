"""
Клиент для работы с 3x-ui панелью через REST API.
Поддерживает несколько серверов.
"""
import uuid
import json
import time
import secrets
import aiohttp
from typing import Optional
from config import SERVERS


class XUIClient:
    def __init__(self, server_key: str = "de1") -> None:
        self.server_key = server_key
        self.server = SERVERS[server_key]
        self.base_url = self.server["xui_host"]
        self.username = self.server["xui_username"]
        self.password = self.server["xui_password"]
        self.inbound_id = self.server["xui_inbound_id"]
        self.domain = self.server["domain"]
        self.port = self.server["port"]
        self.sub_port = self.server.get("sub_port", 2096)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            jar = aiohttp.CookieJar(unsafe=True)
            self._session = aiohttp.ClientSession(
                cookie_jar=jar,
                connector=aiohttp.TCPConnector(ssl=False),
            )
        return self._session

    async def _reset_session(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def login(self) -> bool:
        session = await self._get_session()
        try:
            resp = await session.post(
                f"{self.base_url}/login",
                data={"username": self.username, "password": self.password},
            )
            text = await resp.text()
            if not text.strip():
                print(f"[XUI:{self.server_key}] Login: пустой ответ")
                return False
            data = json.loads(text)
            success = data.get("success", False)
            if not success:
                print(f"[XUI:{self.server_key}] Login failed: {data.get('msg')}")
            return success
        except Exception as e:
            print(f"[XUI:{self.server_key}] Login error: {e}")
            return False

    async def get_inbound(self) -> Optional[dict]:
        session = await self._get_session()
        try:
            resp = await session.get(
                f"{self.base_url}/panel/api/inbounds/get/{self.inbound_id}"
            )
            text = await resp.text()
            if not text.strip():
                return None
            data = json.loads(text)
            if data.get("success"):
                return data["obj"]
        except Exception as e:
            print(f"[XUI:{self.server_key}] Get inbound error: {e}")
        return None

    async def add_client(self, tg_id: int, plan_key: str, expire_days: int) -> dict:
        await self._reset_session()
        logged = await self.login()
        if not logged:
            raise RuntimeError(f"Не удалось авторизоваться в x-ui ({self.server_key})")

        client_uuid = str(uuid.uuid4())
        email = f"de{'2' if self.server_key == 'de2' else '1'}_{tg_id}"
        expire_ms = int((time.time() + expire_days * 24 * 60 * 60) * 1000)
        remark = f"{self.server['emoji']} {self.server['location']}"
        sub_id = secrets.token_hex(8)

        inbound = await self.get_inbound()
        protocol = inbound.get("protocol", "vless") if inbound else "vless"

        client_settings = {
            "clients": [{
                "id": client_uuid,
                "email": email,
                "enable": True,
                "expiryTime": expire_ms,
                "totalGB": 0,
                "flow": "xtls-rprx-vision" if protocol == "vless" else "",
                "limitIp": 0,
                "subId": sub_id,
                "tgId": str(tg_id),
                "comment": remark,
            }]
        }

        session = await self._get_session()
        try:
            resp = await session.post(
                f"{self.base_url}/panel/api/inbounds/addClient",
                json={"id": self.inbound_id, "settings": json.dumps(client_settings)},
            )
            text = await resp.text()
            if not text.strip():
                raise RuntimeError("Пустой ответ от x-ui")
            data = json.loads(text)
            if not data.get("success"):
                raise RuntimeError(f"x-ui ошибка: {data.get('msg')}")

            # Проверяем subId
            traffic = await self.get_client_traffic(email)
            if traffic and not traffic.get("subId"):
                await self._update_client_sub_id(
                    client_uuid, email, expire_ms, protocol, sub_id, str(tg_id)
                )
        except Exception as e:
            print(f"[XUI:{self.server_key}] Add client error: {e}")
            raise

        link = await self._build_link(protocol, client_uuid, email, inbound, remark)
        sub_link = f"https://{self.domain}:{self.sub_port}/sub/{sub_id}"

        return {
            "uuid": client_uuid,
            "email": email,
            "protocol": protocol,
            "link": link,
            "sub_link": sub_link,
            "sub_id": sub_id,
            "server_key": self.server_key,
        }

    async def _update_client_sub_id(
        self, client_uuid: str, email: str, expire_ms: int,
        protocol: str, sub_id: str, tg_id: str
    ) -> None:
        session = await self._get_session()
        update_settings = {
            "clients": [{
                "id": client_uuid, "email": email, "enable": True,
                "expiryTime": expire_ms, "totalGB": 0,
                "flow": "xtls-rprx-vision" if protocol == "vless" else "",
                "limitIp": 0, "subId": sub_id, "tgId": tg_id,
            }]
        }
        try:
            resp = await session.post(
                f"{self.base_url}/panel/api/inbounds/updateClient/{client_uuid}",
                json={"id": self.inbound_id, "settings": json.dumps(update_settings)},
            )
            text = await resp.text()
            data = json.loads(text)
            if data.get("success"):
                print(f"[XUI:{self.server_key}] subId обновлён для {email}")
        except Exception as e:
            print(f"[XUI:{self.server_key}] Update subId error: {e}")

    async def _build_link(
        self, protocol: str, client_uuid: str, email: str,
        inbound: Optional[dict], remark: str = "",
    ) -> str:
        import base64, urllib.parse

        if inbound is None:
            return ""

        port = inbound.get("port", self.port)
        stream_settings = json.loads(inbound.get("streamSettings", "{}"))
        network = stream_settings.get("network", "tcp")
        security = stream_settings.get("security", "none")

        if protocol == "vless":
            params = f"type={network}&security={security}"
            if security == "reality":
                reality = stream_settings.get("realitySettings", {})
                public_key = reality.get("settings", {}).get("publicKey", "")
                short_id = reality.get("shortIds", [""])[0]
                server_name = reality.get("serverNames", [""])[0]
                params += (
                    f"&pbk={public_key}&sid={short_id}"
                    f"&sni={server_name}&fp=chrome&flow=xtls-rprx-vision"
                )
            elif security == "tls":
                tls = stream_settings.get("tlsSettings", {})
                sni = tls.get("serverName", self.domain)
                params += f"&sni={sni}"
            if network == "ws":
                ws = stream_settings.get("wsSettings", {})
                params += f"&path={ws.get('path', '/')}"
            elif network == "grpc":
                grpc = stream_settings.get("grpcSettings", {})
                params += f"&serviceName={grpc.get('serviceName', '')}&mode=gun"

            display = remark if remark else email
            link = f"vless://{client_uuid}@{self.domain}:{port}?{params}#{urllib.parse.quote(display)}"

        elif protocol == "vmess":
            vmess_config = {
                "v": "2", "ps": remark if remark else email,
                "add": self.domain, "port": str(port), "id": client_uuid,
                "aid": "0", "scy": "auto", "net": network, "type": "none",
                "host": "", "path": "",
                "tls": security if security == "tls" else "",
                "sni": "", "alpn": "", "fp": "",
            }
            if network == "ws":
                ws = stream_settings.get("wsSettings", {})
                vmess_config["path"] = ws.get("path", "/")
            encoded = base64.b64encode(json.dumps(vmess_config).encode()).decode()
            link = f"vmess://{encoded}"
        else:
            link = ""

        return link

    async def delete_client(self, client_uuid: str) -> bool:
        await self._reset_session()
        if not await self.login():
            return False
        session = await self._get_session()
        try:
            resp = await session.post(
                f"{self.base_url}/panel/api/inbounds/{self.inbound_id}/delClient/{client_uuid}"
            )
            data = json.loads(await resp.text())
            return data.get("success", False)
        except Exception as e:
            print(f"[XUI:{self.server_key}] Delete client error: {e}")
            return False

    async def get_client_traffic(self, email: str) -> Optional[dict]:
        await self._reset_session()
        if not await self.login():
            return None
        session = await self._get_session()
        try:
            resp = await session.get(
                f"{self.base_url}/panel/api/inbounds/getClientTraffics/{email}"
            )
            data = json.loads(await resp.text())
            if data.get("success"):
                return data.get("obj")
        except Exception as e:
            print(f"[XUI:{self.server_key}] Get traffic error: {e}")
        return None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


# Синглтоны для каждого сервера
_clients: dict[str, XUIClient] = {}


def get_xui_client(server_key: str = "de1") -> XUIClient:
    if server_key not in _clients:
        _clients[server_key] = XUIClient(server_key)
    return _clients[server_key]


# Обратная совместимость
xui = get_xui_client("de1")
