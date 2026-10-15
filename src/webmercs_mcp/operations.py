"""Write operations and schemas from the bundled Webmercs OpenAPI contract."""

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker

from .policy import WRITE_TOOLS


def load_spec() -> dict[str, Any]:
    resource = files("webmercs_mcp").joinpath("admin-openapi.json")
    if resource.is_file():
        return json.loads(resource.read_text(encoding="utf-8"))
    # Editable installations use the documentation copy directly.
    return json.loads(
        (Path(__file__).resolve().parents[2] / "docs/admin-openapi.json").read_text(
            encoding="utf-8"
        )
    )


SPEC = load_spec()


def json_schema(value: Any) -> Any:
    """Inline local references and translate OpenAPI 3.0 to JSON Schema 2020-12."""
    if isinstance(value, list):
        return [json_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    if "$ref" in value:
        ref = value["$ref"]
        if not ref.startswith("#/components/schemas/"):
            raise ValueError("Only local schema references are supported.")
        return json_schema(SPEC["components"]["schemas"][ref.rsplit("/", 1)[1]])
    result = {key: json_schema(item) for key, item in value.items() if key != "nullable"}
    for bound in ("Minimum", "Maximum"):
        exclusive = "exclusive" + bound
        if isinstance(result.get(exclusive), bool):
            enabled = result.pop(exclusive)
            if enabled:
                result[exclusive] = result.pop(bound.lower())
    if value.get("nullable"):
        return {"anyOf": [result, {"type": "null"}]}
    return result


def check_project(value: Any, project_id: int) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() == "projectid" and (type(item) is not int or item != project_id):
                raise ValueError("Payloadin projektitunniste ei vastaa palvelimen projektia.")
            check_project(item, project_id)
    elif isinstance(value, list):
        for item in value:
            check_project(item, project_id)


@dataclass(frozen=True)
class WriteOperation:
    name: str
    method: str
    path: str
    description: str
    path_parameters: dict[str, dict[str, Any]]
    media_type: str | None
    payload_schema: dict[str, Any] | None

    def prepare(self, arguments: dict[str, Any], project_id: int) -> tuple[str, dict, Any]:
        expected = set(self.path_parameters)
        if self.media_type == "application/json":
            expected.add("payload")
        elif self.media_type == "text/plain":
            expected.add("text")
        elif self.media_type == "multipart/form-data":
            expected.update({"filename", "content_base64"})
        if set(arguments) != expected:
            raise ValueError("Kirjoitustyökalun argumentit eivät vastaa määriteltyjä parametreja.")
        path = self.path
        for key, schema in self.path_parameters.items():
            value = arguments[key]
            if schema.get("format") == "uuid":
                try:
                    value = str(UUID(str(value)))
                except ValueError:
                    raise ValueError("Lähetyksen tunnisteen pitää olla UUID.") from None
            elif type(value) is not int or value <= 0:
                raise ValueError("Tietueen tunnisteen pitää olla positiivinen kokonaisluku.")
            path = path.replace("{" + key + "}", str(value))
        if self.media_type == "application/json":
            payload = arguments["payload"]
            check_project(payload, project_id)
            validator = Draft202012Validator(self.payload_schema, format_checker=FormatChecker())
            error = next(validator.iter_errors(payload), None)
            if error:
                # Do not include rejected values: they may contain personal data or passwords.
                location = ".".join(str(part) for part in error.absolute_path) or "payload"
                raise ValueError(f"Virheellinen payload: {location} ({error.validator}).")
            if self.name == "update_order":
                action_schema = json_schema(
                    SPEC["components"]["schemas"]["SetAdminCommentOrderAction"]
                )
                for action in payload["actions"]:
                    if action["actionType"] != "setAdminComment":
                        raise ValueError(
                            "update_order tukee vain dokumentoitua setAdminComment-toimintoa."
                        )
                    if not Draft202012Validator(action_schema).is_valid(action["payload"]):
                        raise ValueError("Virheellinen setAdminComment-payload.")
            return path, {"json": payload}, payload
        if self.media_type == "text/plain":
            text = arguments["text"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Tuotavan tilaustekstin pitää olla ei-tyhjä merkkijono.")
            if len(text.encode("utf-8")) > 5 * 1024 * 1024:
                raise ValueError("Tuotavan sisällön enimmäiskoko on 5 MiB.")
            return (
                path,
                {"content": text.encode("utf-8"), "headers": {"Content-Type": "text/plain"}},
                text,
            )
        if self.media_type == "multipart/form-data":
            filename = arguments["filename"]
            encoded = arguments["content_base64"]
            if not isinstance(filename, str) or not re.fullmatch(
                r"[A-Za-z0-9_.-]{1,128}", filename
            ):
                raise ValueError(
                    "Anna pelkkä tiedostonimi (kirjaimet, numerot, piste, alaviiva, viiva)."
                )
            if not isinstance(encoded, str) or len(encoded) > 7 * 1024 * 1024:
                raise ValueError("Tuotavan sisällön enimmäiskoko on 5 MiB.")
            try:
                content = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error):
                raise ValueError("content_base64 ei ole kelvollinen Base64-merkkijono.") from None
            if not content or len(content) > 5 * 1024 * 1024:
                raise ValueError("Tuotavan sisällön pitää olla 1 tavun ja 5 MiB:n välillä.")
            preview = {
                "filename": filename,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            return (
                path,
                {"files": {"orderFile": (filename, content, "application/octet-stream")}},
                preview,
            )
        return path, {}, None


def build_operations() -> dict[str, WriteOperation]:
    operations = {}
    for path, methods in SPEC["paths"].items():
        for method, operation in methods.items():
            if method not in {"post", "put", "patch", "delete"}:
                continue
            name = re.sub(r"(?<!^)(?=[A-Z])", "_", operation["operationId"]).lower()
            content = operation.get("requestBody", {}).get("content", {})
            media_type = next(iter(content), None)
            operations[name] = WriteOperation(
                name=name,
                method=method.upper(),
                path=path,
                description=operation.get("summary", name),
                path_parameters={
                    item["name"]: item["schema"]
                    for item in operation.get("parameters", [])
                    if item["in"] == "path"
                },
                media_type=media_type,
                payload_schema=json_schema(content[media_type]["schema"]) if media_type else None,
            )
    if set(operations) != WRITE_TOOLS:
        raise ValueError("OpenAPI write operations and tool policy do not match.")
    return operations


WRITE_OPERATIONS = build_operations()
