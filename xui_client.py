"""
Клиент для работы с 3x-ui панелью через REST API.
Поддерживает VLESS + Reality и VMess протоколы.
"""
import uuid
import json
import aiohttp
from typing import Optional
from config import XUI_HOST, XUI_USERNAME, XUI_PASSWORD, XUI_INBOUND_ID, VPN_DOMAIN, VPN_PORT


class XUIClient:
    def __init__(self) -> None:
        self.base_url = XUI_HOST
        self.session: Optional[aiohttp.ClientSession] = None
        self._cookies: Optional[aiohttp.CookieJar] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False)
            )
        return self.session

    async def login(self) -> bool:
        """
        3x-ui принимает логин как JSON (не form-data).
        content_type=None нужен чтобы aiohttp не падал на нестандартный mimetype.
        """
        session = await self._get_session()
        try:
            resp = await session.post(
                f"{self.base_url}/login",
                json={"username": XUI_USERNAME, "password": XUI_PASSWORD},
            )
            data = await resp.json(content_type=None)
            success = data.get("success", False)
            if not success:
                print(f"[XUI] Login failed: {data.get('msg', 'unknown')}")
            return success
        except Exception as e:
            print(f"[XUI] Login error: {e}")
            return False

    async def get_inbound(self) -> Optional[dict]:
        session = await self._get_session()
        try:
            resp = await session.get(f"{self.base_url}/xui/API/inbounds/get/{XUI_INBOUND_ID}")
            data = await resp.json(content_type=None)
            if data.get("success"):
                return data["obj"]
        except Exception as e:
            print(f"[XUI] Get inbound error: {e}")
        return None

    async def add_client(
        self,
        tg_id: int,
        plan_key: str,
        expire_days: int,
    ) -> Optional[dict]:
        """
        Добавляет нового клиента в inbound.
        Возвращает dict с uuid, email и ссылкой для подключения.
        """
        logged = await self.login()
        if not logged:
            raise RuntimeError("Не удалось авторизоваться в x-ui панели")

        client_uuid = str(uuid.uuid4())
        email = f"tg_{tg_id}_{plan_key}"
        expire_ms = expire_days * 24 * 60 * 60 * 1000  # milliseconds

        # Получаем текущий inbound чтобы узнать протокол
        inbound = await self.get_inbound()
        protocol = inbound.get("protocol", "vless") if inbound else "vless"

        client_settings = {
            "clients": [
                {
                    "id": client_uuid,
                    "email": email,
                    "enable": True,
                    "expiryTime": expire_ms,
                    "totalGB": 0,  # 0 = безлимит
                    "flow": "xtls-rprx-vision" if protocol == "vless" else "",
                    "limitIp": 3,
                }
            ]
        }

        session = await self._get_session()
        try:
            resp = await session.post(
                f"{self.base_url}/xui/API/inbounds/addClient",
                json={
                    "id": XUI_INBOUND_ID,
                    "settings": json.dumps(client_settings),
                },
            )
            data = await resp.json(content_type=None)
            if not data.get("success"):
                raise RuntimeError(f"x-ui ответил ошибкой: {data.get('msg')}")
        except Exception as e:
            print(f"[XUI] Add client error: {e}")
            raise

        # Строим ссылку подключения
        link = await self._build_link(protocol, client_uuid, email, inbound)

        return {
            "uuid": client_uuid,
            "email": email,
            "protocol": protocol,
            "link": link,
        }

    async def _build_link(
        self,
        protocol: str,
        client_uuid: str,
        email: str,
        inbound: Optional[dict],
    ) -> str:
        """Строит ссылку vless:// или vmess:// для клиента."""
        import base64

        if inbound is None:
            return ""

        port = inbound.get("port", VPN_PORT)
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
                params += f"&pbk={public_key}&sid={short_id}&sni={server_name}&fp=chrome&flow=xtls-rprx-vision"
            elif security == "tls":
                tls = stream_settings.get("tlsSettings", {})
                sni = tls.get("serverName", VPN_DOMAIN)
                params += f"&sni={sni}"

            if network == "ws":
                ws = stream_settings.get("wsSettings", {})
                path = ws.get("path", "/")
                params += f"&path={path}"
            elif network == "grpc":
                grpc = stream_settings.get("grpcSettings", {})
                service = grpc.get("serviceName", "")
                params += f"&serviceName={service}&mode=gun"

            link = f"vless://{client_uuid}@{VPN_DOMAIN}:{port}?{params}#{email}"

        elif protocol == "vmess":
            vmess_config = {
                "v": "2",
                "ps": email,
                "add": VPN_DOMAIN,
                "port": str(port),
                "id": client_uuid,
                "aid": "0",
                "scy": "auto",
                "net": network,
                "type": "none",
                "host": "",
                "path": "",
                "tls": security if security == "tls" else "",
                "sni": "",
                "alpn": "",
                "fp": "",
            }
            if network == "ws":
                ws = stream_settings.get("wsSettings", {})
                vmess_config["path"] = ws.get("path", "/")
            encoded = base64.b64encode(
                json.dumps(vmess_config).encode()
            ).decode()
            link = f"vmess://{encoded}"
        else:
            link = ""

        return link

    async def delete_client(self, client_uuid: str) -> bool:
        """Удаляет клиента из inbound (при истечении подписки)."""
        logged = await self.login()
        if not logged:
            return False
        session = await self._get_session()
        try:
            resp = await session.post(
                f"{self.base_url}/xui/API/inbounds/{XUI_INBOUND_ID}/delClient/{client_uuid}"
            )
            data = await resp.json(content_type=None)
            return data.get("success", False)
        except Exception as e:
            print(f"[XUI] Delete client error: {e}")
            return False

    async def get_client_traffic(self, email: str) -> Optional[dict]:
        """Возвращает статистику трафика клиента."""
        logged = await self.login()
        if not logged:
            return None
        session = await self._get_session()
        try:
            resp = await session.get(
                f"{self.base_url}/xui/API/inbounds/getClientTraffics/{email}"
            )
            data = await resp.json(content_type=None)
            if data.get("success"):
                return data.get("obj")
        except Exception as e:
            print(f"[XUI] Get traffic error: {e}")
        return None

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()


# Singleton
xui = XUIClient()
