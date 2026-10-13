"""Only GET requests to a fixed set of Webmercs resources are supported."""

from typing import Any

import httpx

from .config import API_BASE_URL, PROJECT_ID, Settings

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
            raise ValueError("Projektia ei voi muuttaa: käytössä on Frendy (3).")
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
        try:
            async with httpx.AsyncClient(
                base_url=API_BASE_URL + "/",
                auth=httpx.BasicAuth(self.settings.username, self.settings.password),
                headers={"X-Project-ID": str(PROJECT_ID), "Accept": "application/json"},
                timeout=self.settings.timeout_seconds,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = await client.get(path.lstrip("/"), params=params)
        except httpx.TimeoutException:
            raise WebmercsError("Webmercs-haku aikakatkaistiin. Kokeile uudelleen.") from None
        except httpx.RequestError:
            raise WebmercsError("Webmercs API:in ei saatu yhteyttä.") from None
        if not response.is_success:
            messages = {
                401: "Webmercs hylkäsi API-tunnukset (HTTP 401).",
                403: "API-tunnuksilla ei ole oikeutta tähän hakuun tai projektiin (HTTP 403).",
                404: "Tietuetta tai API-resurssia ei löytynyt (HTTP 404).",
                429: "Webmercsin kutsuraja ylittyi (HTTP 429). Odota ennen uutta hakua.",
            }
            raise WebmercsError(
                messages.get(
                    response.status_code,
                    f"Webmercs-haku epäonnistui (HTTP {response.status_code}).",
                )
            )
        try:
            data = response.json()
        except ValueError:
            raise WebmercsError("Webmercs palautti virheellisen JSON-vastauksen.") from None
        if not isinstance(data, dict):
            raise WebmercsError("Webmercs palautti odottamattoman vastausrakenteen.")
        return data
