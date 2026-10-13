import base64
import json
from pathlib import Path

import httpx
import pytest

from webmercs_mcp.client import WebmercsClient, WebmercsError
from webmercs_mcp.config import Settings


def make_client(handler):
    return WebmercsClient(
        Settings("test-user", "test-password"), transport=httpx.MockTransport(handler)
    )


async def test_auth_scope_path_and_query_match_openapi():
    spec = json.loads((Path(__file__).parents[1] / "docs/admin-openapi.json").read_text())

    def handler(request):
        assert request.method == "GET"
        assert str(request.url).startswith("https://api.webmercs.com/admin/v1/orders?")
        assert request.headers["X-Project-ID"] == "3"
        expected = base64.b64encode(b"test-user:test-password").decode()
        assert request.headers["Authorization"] == f"Basic {expected}"
        assert request.url.params["pendingExportAny"] == "false"
        assert request.url.params["serialNumber"] == "SN & / +"
        documented = {p["name"] for p in spec["paths"]["/orders"]["get"]["parameters"]}
        assert set(request.url.params).issubset(documented)
        return httpx.Response(200, json={"items": [], "total": 0})

    result = await make_client(handler).get(
        "orders",
        serialNumber="SN & / +",
        createdAtDays=1825,
        pendingExportAny=False,
        offset=0,
        limit=20,
        customerId=None,
    )
    assert result == {"items": [], "total": 0}


@pytest.mark.parametrize(
    "filters",
    [{"projectId": 4}, {"limit": 101}, {"offset": -1}, {"createdAtDays": 0}, {"serialNumber": " "}],
)
async def test_invalid_inputs_never_make_request(filters):
    def handler(request):
        pytest.fail("Invalid input reached HTTP transport")

    with pytest.raises(ValueError):
        await make_client(handler).get("orders", **filters)


async def test_unapproved_resource_and_nonpositive_id_are_blocked():
    def handler(request):
        pytest.fail("Invalid path reached HTTP transport")

    client = make_client(handler)
    with pytest.raises(ValueError):
        await client.get("../projects")
    with pytest.raises(ValueError):
        await client.get("orders", 0)


@pytest.mark.parametrize("status", [301, 401, 403, 404, 429, 500])
async def test_upstream_errors_do_not_expose_response_body(status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status, text="private upstream details", headers={"Location": "https://example.com"}
        )

    with pytest.raises(WebmercsError) as error:
        await make_client(handler).get("orders", 123)
    assert str(status) in str(error.value)
    assert "private" not in str(error.value)
    assert "test-password" not in str(error.value)
    assert len(requests) == 1


async def test_timeout_and_bad_json_are_safe():
    def timeout(request):
        raise httpx.ReadTimeout("private details", request=request)

    with pytest.raises(WebmercsError, match="aikakatkaistiin"):
        await make_client(timeout).get("orders", 123)
    with pytest.raises(WebmercsError, match="JSON"):
        await make_client(lambda _: httpx.Response(200, text="not json")).get("orders", 123)


def test_credentials_are_required_and_hidden_in_repr():
    with pytest.raises(ValueError):
        Settings("", "")
    assert "test-password" not in repr(Settings("test-user", "test-password"))
    with pytest.raises(ValueError):
        Settings("user", "password", float("nan"))
