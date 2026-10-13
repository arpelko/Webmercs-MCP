import json
import sys
from pathlib import Path

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.memory import create_connected_server_and_client_session

from webmercs_mcp.client import WebmercsClient
from webmercs_mcp.config import Settings
from webmercs_mcp.server import create_server


async def test_tools_over_mcp_and_openapi_contract():
    spec = json.loads((Path(__file__).parents[1] / "docs/admin-openapi.json").read_text())
    requests = []

    def handler(request):
        requests.append(request)
        path = request.url.path.removeprefix("/admin/v1")
        contract_path = (
            path
            if path in spec["paths"]
            else path.rsplit("/", 1)[0]
            + "/{"
            + {
                "orders": "orderId",
                "vendororders": "vendorOrderId",
                "products": "productId",
                "customers": "customerId",
                "users": "userId",
            }[path.split("/")[1]]
            + "}"
        )
        operation = spec["paths"][contract_path]["get"]
        assert set(request.url.params).issubset({p["name"] for p in operation["parameters"]})
        assert request.headers["X-Project-ID"] == "3"
        assert request.method == "GET"
        return httpx.Response(200, json={"items": [], "total": 0})

    server = create_server(
        WebmercsClient(Settings("test", "test"), transport=httpx.MockTransport(handler))
    )
    cases = {
        "list_orders": {"pending_export_any": True},
        "get_order": {"order_id": 123},
        "find_orders_by_serial_number": {"serial_number": "SN-123", "created_at_days": 1825},
        "list_vendor_orders": {"vendor_id": 10},
        "get_vendor_order": {"vendor_order_id": 123},
        "search_products": {"brand_sku": "SKU-123"},
        "get_product": {"product_id": 123},
        "list_customers": {"customer_number": "C-123"},
        "get_customer": {"customer_id": 123},
        "list_users": {"email": "test@example.com", "enabled": False},
        "get_user": {"user_id": 123},
    }
    async with create_connected_server_and_client_session(server._mcp_server) as session:
        listed = await session.list_tools()
        assert {t.name for t in listed.tools} == set(cases)
        for tool in listed.tools:
            assert tool.annotations.readOnlyHint is True
            assert "project_id" not in tool.inputSchema.get("properties", {})
        for name, arguments in cases.items():
            result = await session.call_tool(name, arguments)
            assert not result.isError
            assert result.structuredContent == {"items": [], "total": 0}
        result = await session.call_tool("list_orders", {"limit": 101})
        assert result.isError
    assert len(requests) == len(cases)
    serial_request = requests[2]
    assert serial_request.url.params["serialNumber"] == "SN-123"
    assert serial_request.url.params["createdAtDays"] == "1825"


async def test_cli_stdio_startup_from_another_directory(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("WEBMERCS_API_USERNAME=test\nWEBMERCS_API_PASSWORD=test\n")
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "webmercs_mcp", "--env-file", str(env_file)],
        cwd=str(tmp_path),
    )
    # Initialization and tool discovery never call the upstream API.
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            assert initialized.serverInfo.name == "Frendy Webmercs"
            result = await session.list_tools()
            assert len(result.tools) == 11
