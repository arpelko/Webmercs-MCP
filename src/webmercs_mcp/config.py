"""Configuration: credentials stay on the server; project scope is fixed."""

import math
import os
from dataclasses import dataclass, field

API_BASE_URL = "https://api.webmercs.com/admin/v1"
PROJECT_ID = 3


@dataclass(frozen=True)
class Settings:
    username: str = field(repr=False)
    password: str = field(repr=False)
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.username.strip() or not self.password.strip():
            raise ValueError(
                "Aseta WEBMERCS_API_USERNAME ja WEBMERCS_API_PASSWORD .env-tiedostoon."
            )
        if ":" in self.username:
            raise ValueError("Basic Auth -käyttäjätunnus ei voi sisältää kaksoispistettä.")
        if not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 120:
            raise ValueError("WEBMERCS_TIMEOUT_SECONDS pitää olla suurempi kuin 0 ja enintään 120.")

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            timeout = float(os.getenv("WEBMERCS_TIMEOUT_SECONDS", "30"))
        except ValueError:
            raise ValueError("WEBMERCS_TIMEOUT_SECONDS pitää olla numero.") from None
        return cls(
            username=os.getenv("WEBMERCS_API_USERNAME", ""),
            password=os.getenv("WEBMERCS_API_PASSWORD", ""),
            timeout_seconds=timeout,
        )
