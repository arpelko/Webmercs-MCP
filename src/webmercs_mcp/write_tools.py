"""Expose each permitted API write as a separate MCP tool with its actual schema."""

import inspect
import re
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field, WithJsonSchema

from .client import WebmercsClient, WebmercsError
from .operations import WRITE_OPERATIONS, WriteOperation


def make_write_tool(client: WebmercsClient, operation: WriteOperation):
    names = {re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower(): key for key in operation.path_parameters}

    async def execute(**arguments: Any) -> dict[str, Any]:
        dry_run = arguments.pop("dry_run", True)
        arguments = {names.get(key, key): value for key, value in arguments.items()}
        try:
            return await client.write(operation.name, arguments, dry_run=dry_run)
        except (ValueError, WebmercsError) as exc:
            raise ToolError(str(exc)) from None

    parameters = []
    for public_name, api_name in names.items():
        schema = operation.path_parameters[api_name]
        annotation = (
            UUID if schema.get("format") == "uuid" else Annotated[int, Field(gt=0, strict=True)]
        )
        parameters.append(
            inspect.Parameter(public_name, inspect.Parameter.KEYWORD_ONLY, annotation=annotation)
        )
    if operation.media_type == "application/json":
        annotation = Annotated[dict[str, Any], WithJsonSchema(operation.payload_schema)]
        parameters.append(
            inspect.Parameter("payload", inspect.Parameter.KEYWORD_ONLY, annotation=annotation)
        )
    elif operation.media_type == "text/plain":
        parameters.append(inspect.Parameter("text", inspect.Parameter.KEYWORD_ONLY, annotation=str))
    elif operation.media_type == "multipart/form-data":
        parameters.extend(
            [
                inspect.Parameter("filename", inspect.Parameter.KEYWORD_ONLY, annotation=str),
                inspect.Parameter("content_base64", inspect.Parameter.KEYWORD_ONLY, annotation=str),
            ]
        )
    parameters.append(
        inspect.Parameter(
            "dry_run",
            inspect.Parameter.KEYWORD_ONLY,
            default=True,
            annotation=Annotated[bool, Field(strict=True)],
        )
    )
    execute.__name__ = operation.name
    execute.__signature__ = inspect.Signature(parameters, return_annotation=dict[str, Any])
    execute.__doc__ = (
        f"{operation.description}. {operation.method} {operation.path}. "
        "Defaults to dry_run=true: validates and previews without an API call. "
        "To execute, set dry_run=false and enable WEBMERCS_ALLOW_WRITES on the server. "
        "Payload field names, required fields and null semantics follow the input schema. "
        "Do not retry an uncertain result without checking whether the change was applied."
    )
    return execute


def register_write_tools(mcp: FastMCP, client: WebmercsClient) -> None:
    for name, operation in WRITE_OPERATIONS.items():
        if name in client.settings.policy.enabled_tools:
            mcp.add_tool(
                make_write_tool(client, operation),
                annotations=ToolAnnotations(
                    readOnlyHint=False,
                    destructiveHint=True,
                    idempotentHint=False,
                ),
            )
