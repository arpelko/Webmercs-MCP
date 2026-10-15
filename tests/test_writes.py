import base64
import json

import httpx
import pytest
from jsonschema import Draft202012Validator
from mcp.shared.memory import create_connected_server_and_client_session

from webmercs_mcp.client import WebmercsClient, WebmercsError
from webmercs_mcp.config import Settings
from webmercs_mcp.operations import SPEC, WRITE_OPERATIONS
from webmercs_mcp.policy import PACKAGES, ToolPolicy
from webmercs_mcp.server import create_server


def client(handler, package="full", writes=True, disabled=frozenset()):
    return WebmercsClient(
        Settings("test", "secret", 42, policy=ToolPolicy(package, writes, disabled)),
        transport=httpx.MockTransport(handler),
    )


def no_request(request):
    pytest.fail("Request must not reach Webmercs")


@pytest.mark.parametrize("package", list(PACKAGES))
async def test_package_discovery_and_direct_call_enforcement(package):
    api = client(no_request, package=package)
    mcp = create_server(api)
    async with create_connected_server_and_client_session(mcp._mcp_server) as session:
        discovered = await session.list_tools()
        assert {tool.name for tool in discovered.tools} == api.settings.policy.enabled_tools
        if package != "none":
            info = await session.call_tool("list_tool_packages", {})
            assert info.structuredContent["active_package"] == package
        for name in set(WRITE_OPERATIONS) - api.settings.policy.enabled_tools:
            result = await session.call_tool(name, {"dry_run": False})
            assert result.isError
            with pytest.raises(ValueError):
                await api.write(name, {}, dry_run=False)


async def test_disabled_tool_is_hidden_and_cannot_be_called():
    api = client(no_request, disabled=frozenset({"set_order_status_order_action", "get_order"}))
    async with create_connected_server_and_client_session(
        create_server(api)._mcp_server
    ) as session:
        tools = await session.list_tools()
        assert not {"set_order_status_order_action", "get_order"} & {t.name for t in tools.tools}
        for name in ("set_order_status_order_action", "get_order"):
            result = await session.call_tool(name, {"order_id": 123})
            assert result.isError
    with pytest.raises(ValueError):
        await api.write(
            "set_order_status_order_action",
            {"orderId": 123, "payload": {"orderStatus": "Ordered"}},
            dry_run=False,
        )


async def test_preview_and_execution_gate():
    api = client(no_request, package="orders", writes=False)
    args = {"orderId": 123, "payload": {"orderStatus": "Ordered"}}
    preview = await api.write("set_order_status_order_action", args)
    assert preview["executed"] is False
    assert preview["path"] == "/orders/123/setOrderStatus"
    assert preview["project_id"] == 42
    assert preview["body"] == {"orderStatus": "Ordered"}
    assert preview["writes_allowed"] is False
    with pytest.raises(ValueError, match="WEBMERCS_ALLOW_WRITES"):
        await api.write("set_order_status_order_action", args, dry_run=False)


@pytest.mark.parametrize(
    "payload",
    [
        {"orderStatus": "not-a-status"},
        {},
        {"orderStatus": "Ordered", "extra": True},
        {"orderStatus": "Ordered", "projectId": 99},
        {"orderStatus": "Ordered", "projectId": None},
    ],
)
async def test_bad_payload_and_project_override_rejected(payload):
    with pytest.raises(ValueError):
        await client(no_request).write(
            "set_order_status_order_action", {"orderId": 123, "payload": payload}, dry_run=False
        )


async def test_null_patch_fields_preserved_and_empty_success_supported():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "PATCH"
        assert json.loads(request.content) == {"adminComment": None}
        assert request.headers["X-Project-ID"] == "42"
        return httpx.Response(200)

    result = await client(handler).write(
        "update_order_partial", {"orderId": 123, "payload": {"adminComment": None}}, dry_run=False
    )
    assert result == {"dry_run": False, "executed": True, "http_status": 200, "data": None}
    assert len(requests) == 1


async def test_uncertain_write_is_not_retried():
    requests = []

    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout("secret", request=request)

    with pytest.raises(WebmercsError, match="voinut toteutua") as error:
        await client(handler).write(
            "update_order_partial", {"orderId": 123, "payload": {}}, dry_run=False
        )
    assert "secret" not in str(error.value)
    assert len(requests) == 1


async def test_unsupported_actions_and_nested_project_override_are_blocked():
    api = client(no_request)
    for action in [
        {"actionType": "setOrderStatus", "payload": {"orderStatus": "Shipped"}},
        {"actionType": "setAdminComment", "payload": {"projectId": 99}},
        {"actionType": "setAdminComment", "payload": {"unsupported": True}},
    ]:
        with pytest.raises(ValueError):
            await api.write("update_order", {"orderId": 123, "payload": {"actions": [action]}})


@pytest.mark.parametrize(
    "arguments",
    [
        {"filename": "../private.xml", "content_base64": "eA=="},
        {"filename": "test.xml", "content_base64": "not base64"},
        {"filename": "test.xml", "content_base64": ""},
    ],
)
async def test_file_import_rejects_paths_and_invalid_content(arguments):
    with pytest.raises(ValueError):
        await client(no_request).write("import_order_file", arguments)


def sample(schema):
    """Produce minimal synthetic values for exercising every documented operation."""
    if "allOf" in schema:
        return sample(schema["allOf"][0])
    if "anyOf" in schema:
        return sample(schema["anyOf"][0])
    if "enum" in schema:
        return schema["enum"][0]
    kind = schema.get("type")
    if kind == "object":
        return {key: sample(schema["properties"][key]) for key in schema.get("required", [])}
    if kind == "array":
        return [sample(schema["items"]) for _ in range(schema.get("minItems", 0))]
    if kind == "boolean":
        return False
    if kind in {"integer", "number"}:
        return max(1, schema.get("minimum", 0), schema.get("exclusiveMinimum", 0) + 1)
    if schema.get("format") == "email":
        return "test@example.com"
    return "X" * max(1, schema.get("minLength", 1))


@pytest.mark.parametrize("name", list(WRITE_OPERATIONS))
async def test_all_write_tools_through_mcp_match_contract(name):
    operation = WRITE_OPERATIONS[name]
    expected_path = operation.path
    args = {}
    for key, schema in operation.path_parameters.items():
        import re

        value = "28bfc6c7-038f-4078-9586-2ebf4ef6c3b4" if schema.get("format") == "uuid" else 123
        expected_path = expected_path.replace("{" + key + "}", str(value))
        args[re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower()] = value
    if operation.media_type == "application/json":
        args["payload"] = sample(operation.payload_schema)
    elif operation.media_type == "text/plain":
        args["text"] = "Synthetic test order document"
    elif operation.media_type == "multipart/form-data":
        args.update(filename="test.xml", content_base64=base64.b64encode(b"<test/>").decode())
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == operation.method
        assert request.url.path == "/admin/v1" + expected_path
        assert request.headers["X-Project-ID"] == "42"
        if "payload" in args:
            assert json.loads(request.content) == args["payload"]
        elif "text" in args:
            assert request.content == args["text"].encode()
            assert request.headers["Content-Type"] == "text/plain"
        elif "content_base64" in args:
            assert 'name="orderFile"' in request.content.decode()
            assert b"<test/>" in request.content
        return httpx.Response(201, json={"id": 456})

    api = client(handler)
    async with create_connected_server_and_client_session(
        create_server(api)._mcp_server
    ) as session:
        tools = await session.list_tools()
        tool = next(t for t in tools.tools if t.name == name)
        Draft202012Validator.check_schema(tool.inputSchema)
        assert tool.annotations.readOnlyHint is False
        assert tool.annotations.destructiveHint is True
        assert tool.inputSchema["properties"]["dry_run"]["default"] is True
        preview = await session.call_tool(name, args)
        assert not preview.isError
        assert preview.structuredContent["executed"] is False
        assert not requests
        result = await session.call_tool(name, {**args, "dry_run": False})
        assert not result.isError, result.content
        assert result.structuredContent["executed"] is True
    assert len(requests) == 1
    assert operation.method.lower() in SPEC["paths"][operation.path]


@pytest.mark.parametrize(
    "variable,value",
    [
        ("MCP_TOOL_PACKAGE", "typo"),
        ("WEBMERCS_ALLOW_WRITES", "yes"),
        ("MCP_DISABLED_TOOLS", "unknown_tool"),
    ],
)
def test_bad_policy_settings_fail_closed(monkeypatch, variable, value):
    monkeypatch.setenv("WEBMERCS_API_USERNAME", "test")
    monkeypatch.setenv("WEBMERCS_API_PASSWORD", "test")
    monkeypatch.setenv("WEBMERCS_PROJECT_ID", "42")
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError):
        Settings.from_env()
