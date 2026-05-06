"""
Клиент для работы с 3x-ui панелью через REST API.
Куки сохраняются через aiohttp.CookieJar между запросами.
"""
import uuid
import json
import aiohttp
from typing import Optional
from config import XUI_HOST, XUI_USERNAME, XUI_PASSWORD, XUI_INBOUND_ID, VPN_DOMAIN, VPN_PORT


class XUIClient:
    def __init__(self) -> None:
        self.base_url = XUI_HOST
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Возвращает сессию с общим CookieJar (куки сохраняются между запросами)."""
        if self._session is None or self._session.closed:
            jar = aiohttp.CookieJar(unsafe=True)  # unsafe=True для IP-адресов
            self._session = aiohttp.ClientSession(
                cookie_jar=jar,
                connector=aiohttp.TCPConnector(ssl=False),
            )
        return self._session

    async def login(self) -> bool:
        session = await self._get_session()
        try:
            resp = await session.post(
                f"{self.base_url}/login",
                data={"username": XUI_USERNAME, "password": XUI_PASSWORD},
            )
            text = await resp.text()
            if not text.strip():
                print("[XUI] Login: пустой ответ")
                return False
            data = json.loads(text)
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
            resp = await session.get(
                f"{self.base_url}/panel/api/inbounds/get/{XUI_INBOUND_ID}"
            )
            text = await resp.text()
            if not text.strip():
                print("[XUI] Get inbound: пустой ответ")
                return None
            data = json.loads(text)
            if data.get("success"):
                return data["obj"]
            print(f"[XUI] Get inbound failed: {data.get('msg')}")
        except Exception as e:
            print(f"[XUI] Get inbound error: {e}")
        return None

    async def add_client(
        self,
        tg_id: int,
        plan_key: str,
        expire_days: int,
    ) -> dict:
        # Каждый раз логинимся заново чтобы куки были свежими
        await self._reset_session()
        logged = await self.login()
        if not logged:
            raise RuntimeError("Не удалось авторизоваться в x-ui панели")

        client_uuid = str(uuid.uuid4())
        email = f"tg_{tg_id}_{plan_key}"
        # expiryTime — абсолютный Unix timestamp в миллисекундах
        import time
        expire_ms = int((time.time() + expire_days * 24 * 60 * 60) * 1000)

        # Красивое имя конфига в приложении
        plan_labels = {
            "trial": "Trial 🆓",
            "1month": "1 Month",
            "3months": "3 Months",
            "6months": "6 Months",
            "1year": "1 Year 👑",
        }
        remark = f"🇩🇪 CookieVPN {plan_labels.get(plan_key, plan_key)}"

        inbound = await self.get_inbound()
        protocol = inbound.get("protocol", "vless") if inbound else "vless"

        # Генерируем subId для ссылки-подписки
        import secrets
        sub_id = secrets.token_hex(8)  # 16 символов
        client_settings = {
            "clients": [
                {
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
                }
            ]
        }

        session = await self._get_session()
        try:
            resp = await session.post(
                f"{self.base_url}/panel/api/inbounds/addClient",
                json={
                    "id": XUI_INBOUND_ID,
                    "settings": json.dumps(client_settings),
                },
            )
            text = await resp.text()
            if not text.strip():
                raise RuntimeError("Пустой ответ от x-ui при добавлении клиента")
            data = json.loads(text)
            if not data.get("success"):
                raise RuntimeError(f"x-ui ошибка: {data.get('msg')}")

            # Проверяем что subId сохранился, если нет — обновляем клиента
            traffic = await self.get_client_traffic(email)
            if traffic and not traffic.get("subId"):
                await self._update_client_sub_id(
                    client_uuid, email, expire_ms, protocol, sub_id, str(tg_id)
                )

        except Exception as e:
            print(f"[XUI] Add client error: {e}")
            raise

        link = await self._build_link(protocol, client_uuid, email, inbound, remark)

        # Ссылка-подписка — приложение автоматически обновляет серверы
        # Формат: https://host/basepath/sub/subId
        base = XUI_HOST.rstrip("/")
        sub_link = f"{base}/sub/{sub_id}"

        return {
            "uuid": client_uuid,
            "email": email,
            "protocol": protocol,
            "link": link,
            "sub_link": sub_link,
            "sub_id": sub_id,
        }

    async def _update_client_sub_id(
        self, client_uuid: str, email: str, expire_ms: int,
        protocol: str, sub_id: str, tg_id: str
    ) -> None:
        """Обновляет subId клиента если он не был сохранён при создании."""
        session = await self._get_session()
        update_settings = {
            "clients": [{
                "id": client_uuid,
                "email": email,
                "enable": True,
                "expiryTime": expire_ms,
                "totalGB": 0,
                "flow": "xtls-rprx-vision" if protocol == "vless" else "",
                "limitIp": 0,
                "subId": sub_id,
                "tgId": tg_id,
            }]
        }
        try:
            resp = await session.post(
                f"{self.base_url}/panel/api/inbounds/updateClient/{client_uuid}",
                json={"id": XUI_INBOUND_ID, "settings": json.dumps(update_settings)},
            )
            text = await resp.text()
            data = json.loads(text)
            if data.get("success"):
                print(f"[XUI] subId обновлён для {email}")
            else:
                print(f"[XUI] Не удалось обновить subId: {data.get('msg')}")
        except Exception as e:
            print(f"[XUI] Update subId error: {e}")

    async def _reset_session(self) -> None:
        """Закрывает старую сессию чтобы куки обновились."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def _build_link(
        self,
        protocol: str,
        client_uuid: str,
        email: str,
        inbound: Optional[dict],
        remark: str = "",
    ) -> str:
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
                params += (
                    f"&pbk={public_key}&sid={short_id}"
                    f"&sni={server_name}&fp=chrome&flow=xtls-rprx-vision"
                )
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

            # remark в конце ссылки — это имя которое показывается в приложении
            display_name = remark if remark else email
            import urllib.parse
            link = f"vless://{client_uuid}@{VPN_DOMAIN}:{port}?{params}#{urllib.parse.quote(display_name)}"

        elif protocol == "vmess":
            vmess_config = {
                "v": "2", "ps": remark if remark else email, "add": VPN_DOMAIN,
                "port": str(port), "id": client_uuid, "aid": "0",
                "scy": "auto", "net": network, "type": "none",
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
        logged = await self.login()
        if not logged:
            return False
        session = await self._get_session()
        try:
            resp = await session.post(
                f"{self.base_url}/panel/api/inbounds/{XUI_INBOUND_ID}/delClient/{client_uuid}"
            )
            text = await resp.text()
            data = json.loads(text)
            return data.get("success", False)
        except Exception as e:
            print(f"[XUI] Delete client error: {e}")
            return False

    async def get_client_traffic(self, email: str) -> Optional[dict]:
        await self._reset_session()
        logged = await self.login()
        if not logged:
            return None
        session = await self._get_session()
        try:
            resp = await session.get(
                f"{self.base_url}/panel/api/inbounds/getClientTraffics/{email}"
            )
            text = await resp.text()
            data = json.loads(text)
            if data.get("success"):
                return data.get("obj")
        except Exception as e:
            print(f"[XUI] Get traffic error: {e}")
        return None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


# Singleton
xui = XUIClient()
