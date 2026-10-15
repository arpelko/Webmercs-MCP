"""HTTP client with fixed routes, project scope and enforced write policy."""

from typing import Any

import httpx

from .config import API_BASE_URL, Settings
from .operations import WRITE_OPERATIONS

RESOURCES = frozenset({"orders", "vendororders", "products", "customers", "users"})


class WebmercsError(Exception):
    """A safe error message without credentials or the upstream response body."""


class WebmercsClient:
    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.settings = settings
        self.transport = transport

    async def get(
        self,
        resource: str,
        record_id: int | None = None,
        **filters: Any,
    ) -> dict[str, Any]:
        if resource not in RESOURCES:
            raise ValueError("Tuntematon resurssi.")
        if record_id is not None and (isinstance(record_id, bool) or record_id <= 0):
            raise ValueError("Tietueen tunnisteen pitää olla positiivinen kokonaisluku.")
        if any(key.lower() == "projectid" for key in filters):
            raise ValueError(
                "Projektia ei voi muuttaa työkalukutsussa; se määritetään asetuksissa."
            )
        params = {key: value for key, value in filters.items() if value is not None}
        if "limit" in params and not 1 <= params["limit"] <= 100:
            raise ValueError("limit pitää olla välillä 1–100.")
        if "offset" in params and params["offset"] < 0:
            raise ValueError("offset ei voi olla negatiivinen.")
        if "createdAtDays" in params and params["createdAtDays"] <= 0:
            raise ValueError("created_at_days pitää olla positiivinen.")
        for key in ("serialNumber", "search", "brandSku", "email", "customerNumber"):
            if key in params and not params[key].strip():
                raise ValueError(f"Hakuehto {key} ei voi olla tyhjä.")
        path = f"/{resource}" if record_id is None else f"/{resource}/{record_id}"
        response = await self._request("GET", path, params=params)
        try:
            data = response.json()
        except ValueError:
            raise WebmercsError("Webmercs palautti virheellisen JSON-vastauksen.") from None
        if not isinstance(data, dict):
            raise WebmercsError("Webmercs palautti odottamattoman vastausrakenteen.")
        return data

    async def write(
        self, name: str, arguments: dict[str, Any], *, dry_run: bool = True
    ) -> dict[str, Any]:
        if type(dry_run) is not bool:
            raise ValueError("dry_run pitää olla totuusarvo.")
        self.settings.policy.require(name, execute_write=not dry_run)
        if name not in WRITE_OPERATIONS:
            raise ValueError("Tuntematon kirjoitustyökalu.")
        operation = WRITE_OPERATIONS[name]
        path, kwargs, preview = operation.prepare(arguments, self.settings.project_id)
        if dry_run:
            return {
                "dry_run": True,
                "executed": False,
                "tool": name,
                "method": operation.method,
                "path": path,
                "project_id": self.settings.project_id,
                "body": preview,
                "writes_allowed": self.settings.policy.allow_writes,
                "note": (
                    "Esikatselu validoi pyynnön paikallisesti; "
                    "API:n oikeuksia tai tietueita ei tarkisteta."
                ),
            }
        response = await self._request(operation.method, path, **kwargs)
        data = None
        if response.content:
            try:
                data = response.json()
            except ValueError:
                raise WebmercsError(
                    "Kirjoitus palautti onnistumistilan mutta virheellisen JSON-vastauksen. "
                    "Tarkista tila ennen uutta yritystä."
                ) from None
        return {
            "dry_run": False,
            "executed": True,
            "http_status": response.status_code,
            "data": data,
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                base_url=API_BASE_URL + "/",
                auth=httpx.BasicAuth(self.settings.username, self.settings.password),
                headers={
                    "X-Project-ID": str(self.settings.project_id),
                    "Accept": "application/json",
                },
                timeout=self.settings.timeout_seconds,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = await client.request(method, path.lstrip("/"), **kwargs)
        except httpx.TimeoutException:
            raise WebmercsError(
                "Webmercs-haku aikakatkaistiin. Kokeile uudelleen."
                if method == "GET"
                else "Kirjoitus aikakatkaistiin. Muutos on voinut toteutua; "
                "tarkista tila ennen uutta yritystä."
            ) from None
        except httpx.RequestError:
            raise WebmercsError(
                "Webmercs API:in ei saatu yhteyttä."
                if method == "GET"
                else "Kirjoituksen yhteys katkesi. Tarkista muutoksen tila ennen uutta yritystä."
            ) from None
        if not response.is_success:
            messages = {
                401: "Webmercs hylkäsi API-tunnukset (HTTP 401).",
                403: "API-tunnuksilla ei ole oikeutta tähän hakuun tai projektiin (HTTP 403).",
                404: "Tietuetta tai API-resurssia ei löytynyt (HTTP 404).",
                429: "Webmercsin kutsuraja ylittyi (HTTP 429). Odota ennen uutta hakua.",
            }
            message = messages.get(
                response.status_code,
                f"Webmercs-pyyntö epäonnistui (HTTP {response.status_code}).",
            )
            if method != "GET" and response.status_code >= 500:
                message += " Muutos on voinut toteutua; tarkista tila ennen uutta yritystä."
            raise WebmercsError(message)
        return response
