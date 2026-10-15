# Webmercs MCP

English | [Suomi](README.FI.md)

A local MCP server for the Webmercs Admin API with 11 read tools, 26 write tools,
and `list_tool_packages` for inspecting the active configuration. Only read tools
are enabled by default.

Every API request is scoped to the project configured in `WEBMERCS_PROJECT_ID`
using the `X-Project-ID` header. Tool calls cannot change the project or API host.
The implementation contains no company-specific identifiers or business rules.

## Installation

Requirements: Python 3.11 or later and Webmercs Admin API credentials.

```bash
cd "/absolute/path/to/webmercs-mcp"
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
```

Set `WEBMERCS_API_USERNAME`, `WEBMERCS_API_PASSWORD`, and `WEBMERCS_PROJECT_ID`
in `.env`. The project ID must be the positive integer identifying your Webmercs
project. Credentials and the project ID are blank in the example file; there is
no default project. Replace the example paths with your actual project directory.

The API uses HTTP Basic Auth. Enter the username and password as provided,
without Base64 encoding or a `Basic ` prefix. If your API keys use a different
format, confirm with Webmercs how they map to the Basic Auth credential pair.

`.env` and other local environment files are excluded by `.gitignore`.
Environment variables take precedence over values in `.env`. Credentials and
upstream error response bodies are not included in application logs or tool errors.

## Running and connecting an MCP client

```bash
.venv/bin/webmercs-mcp --env-file "/absolute/path/to/webmercs-mcp/.env"
```

The server uses **stdio**: an MCP client starts the process and communicates over
its standard input and output. Starting it in a terminal waits for client messages
and does not open an HTTP port. Diagnostics go to stderr.

Example MCP client configuration; the exact format depends on your client:

```json
{
  "mcpServers": {
    "webmercs": {
      "command": "/absolute/path/to/webmercs-mcp/.venv/bin/webmercs-mcp",
      "args": [
        "--env-file",
        "/absolute/path/to/webmercs-mcp/.env"
      ]
    }
  }
}
```

Use absolute paths so startup does not depend on the client's working directory.
Credentials do not need to be copied into the client configuration. Restart the
MCP connection after changing `.env` settings.

## Read tools

| Tool | Purpose / main parameters |
| --- | --- |
| `list_orders` | `customer_id`, `user_id`, `status`, `created_at_days`, `pending_export_any` |
| `get_order` | Get an order by `order_id` |
| `find_orders_by_serial_number` | `serial_number`, `created_at_days` |
| `list_vendor_orders` | `vendor_id`, `status`, `created_at_days` |
| `get_vendor_order` | Get a supplier order by `vendor_order_id` |
| `search_products` | `search`, `brand_sku`, `brand_id`, `category_id`, `status` |
| `get_product` | Get a product by `product_id` |
| `list_customers` | `customer_number`, `enabled` |
| `get_customer` | Get a customer by `customer_id` |
| `list_users` | `email`, `customer_id`, `enabled` |
| `get_user` | Get a user by `user_id` |

All list tools support `offset` (default 0) and `limit` (default 20, allowed range
1–100). Each call returns one page in the original API structure, including
`items`, `total`, `count`, `offset`, and `limit` when supplied by the API.
Increase `offset` by the number of returned items to retrieve the next page.
The server does not automatically download all pages.

Order and supplier order searches default to the **last 90 days**, including
serial number searches. Increase `created_at_days` to find older orders. An empty
result does not prove that a serial number is absent from older orders.
Individual record lookups by ID do not use this time window.

Example tool arguments:

```json
{"serial_number": "EXAMPLE-SERIAL-NUMBER", "created_at_days": 1825, "limit": 20}
```

```json
{"status": "Ordered", "pending_export_any": true, "created_at_days": 90}
```

```json
{"brand_sku": "MANUFACTURER-PART-NUMBER", "limit": 10}
```

Order prices are returned in the API's original units. Documented order prices
use minor currency units: for example, `1025` means `EUR 10.25` when the order's
currency is EUR. Check the API documentation for the units of other fields.
Project-specific product prices and stock information may appear in `projects`.

## Tool management

Settings are loaded at startup. Edit `.env` and restart the MCP connection to apply
changes. A tool cannot switch its package or grant itself write access.

| `MCP_TOOL_PACKAGE` | Available tools |
| --- | --- |
| `readonly` (default) | All 11 read tools |
| `orders` | All read tools and 16 order/shipment write tools |
| `catalog` | Product lookups and product creation |
| `customers` | Customer/user lookups and 9 customer/user write tools |
| `full` | All read and write tools |
| `none` | No tools |

`list_tool_packages` reports the active package, enabled tools, exclusions, and
whether write execution is allowed. It is included in every package except `none`.
An unknown package or invalid setting prevents the server from starting.

For example, enable order tools for previews:

```dotenv
MCP_TOOL_PACKAGE=orders
WEBMERCS_ALLOW_WRITES=false
MCP_DISABLED_TOOLS=send_order_email,delete_order_line,delete_vendor_order_shipment
```

`MCP_DISABLED_TOOLS` is a comma-separated list of tools to exclude. Exclusions
override the package: excluded tools are hidden and cannot be called directly
by name. Restrictions apply to tools; several permitted tools may modify the
same field. Tool packages do not replace Webmercs API permissions.

## Writes and previews

Every write tool defaults to `dry_run: true`. A preview validates the request
locally and returns its method, path, project, and body **without calling the API**.
It does not check record existence, permissions, or Webmercs business rules.

Executing a write requires all of the following:

1. The tool is included in the active package and is not excluded.
2. The server configuration has `WEBMERCS_ALLOW_WRITES=true`.
3. The tool call explicitly sets `dry_run: false`.

Example preview using `set_order_status_order_action` for a fictional order:

```json
{
  "order_id": 123,
  "payload": {"orderStatus": "Ordered"},
  "dry_run": true
}
```

Payloads use the fields defined in the API specification, with validation of types,
required fields, enum values, and additional properties. Each tool's MCP input schema
includes its payload structure. Record ID parameters use snake_case, such as
`order_id`, `order_line_id`, `user_id`, `vendor_order_id`, and `shipment_id`.
Payload keys retain their Webmercs names, such as `orderStatus`.

If a JSON payload includes `projectId`, it must match the configured project.
Omitted fields and explicit `null` values are kept distinct. For example,
`null` can clear a field when using `update_order_partial`.

A successful write returns `executed: true`, `http_status`, and `data`.
An empty successful response returns `data: null`. A network or server error
does not guarantee that the change was not applied. Check the record using a
read tool before retrying. The server never automatically retries writes.

Order creation, imports, and the email tool can trigger Webmercs side effects,
including order confirmation emails. `generate_password_reset_link` returns a
sensitive link that the MCP client receives as part of the tool response.

| Write tool | Webmercs operation |
| --- | --- |
| `update_customer` | Partially update a customer |
| `create_customer` | Create a customer |
| `set_customer_number` | Set a customer number |
| `update_order` | Update an order using actions |
| `update_order_partial` | Partially update an order |
| `place_order` | Place an order |
| `set_admin_comment_order_action` | Set an order admin comment |
| `set_order_status_order_action` | Set an order status |
| `set_export_status_order_action` | Set an export status |
| `send_order_email` | Send an order email to default or specified recipients |
| `update_order_billing_address` | Partially update an order billing address |
| `update_order_shipping_address` | Partially update an order shipping address |
| `add_order_line` | Add an order line |
| `update_order_line` | Update an order line |
| `delete_order_line` | Delete an order line |
| `import_order_file` | Import an order from a file |
| `import_order_text` | Import an order from text |
| `create_product` | Create a product |
| `create_user` | Create a user |
| `change_customer` | Change the customer associated with a user |
| `create_billing_profile` | Create a billing profile |
| `set_customer_number_for_billing_profile` | Set a billing profile customer number |
| `create_shipping_profile` | Create a shipping profile |
| `generate_password_reset_link` | Generate a user password reset link |
| `add_vendor_order_shipment` | Add a shipment to a supplier order |
| `delete_vendor_order_shipment` | Delete a supplier order shipment |

`update_order` supports the `setAdminComment` action documented in the API
specification. Prefer the dedicated tools for individual changes.
`import_order_text` accepts `text`. `import_order_file` accepts a plain `filename`
and `content_base64` (up to 5 MiB); it does not read local file paths.
File import previews return the filename, size, and SHA-256 hash. Webmercs handles
validation of the imported document's internal format and business rules.

## Errors and limitations

- HTTP 401: check the API credentials.
- HTTP 403: check access to the configured project and operation.
- HTTP 404: the record or resource was not found.
- HTTP 429: wait before making another request.
- Connection errors and timeouts are returned as tool errors.

Requests are not automatically retried. The default timeout is 30 seconds and
can be changed in `.env`. API responses may include customer, user, and address
information that the MCP client receives in tool responses.

This version is intended for local use. A shared HTTP service, authentication
for such a service, and background synchronization are outside its scope.

## Development and verification

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
```

Tests use simulated HTTP responses to verify Basic Auth, project scoping,
query parameters, package restrictions, previews, and the methods, paths, and
bodies of all 26 write tools through MCP. Explicit PATCH null values are preserved.
Tests require no real API credentials and make no Webmercs requests.

Verify your credentials and actual response contents using a read tool in your
MCP client. Start with a small request, such as `list_customers` with `limit: 1`.

Dependencies are constrained to compatible major versions. This implementation
uses the MCP SDK v1 FastMCP interface. There is currently no dependency lock file.

## API references

- [Webmercs Swagger](https://api.webmercs.com/admin/v1/swagger/index.html)
- [Webmercs OpenAPI JSON](https://api.webmercs.com/admin/v1/swagger/admin-openapi.json)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

`docs/admin-openapi.json` is a documentation snapshot downloaded on October 13, 2026.
It contains no API credentials or actual order responses.
