"""Configuration: credentials and project scope stay on the server."""

import math
import os
from dataclasses import dataclass, field

from .policy import ToolPolicy

API_BASE_URL = "https://api.webmercs.com/admin/v1"


@dataclass(frozen=True)
class Settings:
    username: str = field(repr=False)
    password: str = field(repr=False)
    project_id: int
    timeout_seconds: float = 30.0
    policy: ToolPolicy = field(default_factory=ToolPolicy)

    def __post_init__(self) -> None:
        if not self.username.strip() or not self.password.strip():
            raise ValueError(
                "Aseta WEBMERCS_API_USERNAME ja WEBMERCS_API_PASSWORD .env-tiedostoon."
            )
        if ":" in self.username:
            raise ValueError("Basic Auth -käyttäjätunnus ei voi sisältää kaksoispistettä.")
        if (
            isinstance(self.project_id, bool)
            or not isinstance(self.project_id, int)
            or self.project_id <= 0
        ):
            raise ValueError("WEBMERCS_PROJECT_ID pitää olla positiivinen kokonaisluku.")
        if not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 120:
            raise ValueError("WEBMERCS_TIMEOUT_SECONDS pitää olla suurempi kuin 0 ja enintään 120.")

    @classmethod
    def from_env(cls) -> "Settings":
        allow_writes = os.getenv("WEBMERCS_ALLOW_WRITES", "false").strip().lower()
        if allow_writes not in {"true", "false"}:
            raise ValueError("WEBMERCS_ALLOW_WRITES pitää olla true tai false.")
        policy = ToolPolicy(
            package=os.getenv("MCP_TOOL_PACKAGE", "readonly").strip(),
            allow_writes=allow_writes == "true",
            disabled_tools=frozenset(
                name.strip()
                for name in os.getenv("MCP_DISABLED_TOOLS", "").split(",")
                if name.strip()
            ),
        )
        try:
            project_id = int(os.environ["WEBMERCS_PROJECT_ID"])
        except (KeyError, ValueError):
            raise ValueError(
                "Aseta WEBMERCS_PROJECT_ID:ksi oman Webmercs-projektisi positiivinen tunniste."
            ) from None
        try:
            timeout = float(os.getenv("WEBMERCS_TIMEOUT_SECONDS", "30"))
        except ValueError:
            raise ValueError("WEBMERCS_TIMEOUT_SECONDS pitää olla numero.") from None
        return cls(
            username=os.getenv("WEBMERCS_API_USERNAME", ""),
            password=os.getenv("WEBMERCS_API_PASSWORD", ""),
            project_id=project_id,
            timeout_seconds=timeout,
            policy=policy,
        )
