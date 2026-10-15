"""Server-side tool packages; unknown settings fail closed."""

from dataclasses import dataclass

READ_TOOLS = frozenset(
    {
        "list_orders",
        "get_order",
        "find_orders_by_serial_number",
        "list_vendor_orders",
        "get_vendor_order",
        "search_products",
        "get_product",
        "list_customers",
        "get_customer",
        "list_users",
        "get_user",
    }
)
ORDER_WRITES = frozenset(
    {
        "update_order",
        "update_order_partial",
        "place_order",
        "set_admin_comment_order_action",
        "set_order_status_order_action",
        "set_export_status_order_action",
        "send_order_email",
        "update_order_billing_address",
        "update_order_shipping_address",
        "add_order_line",
        "update_order_line",
        "delete_order_line",
        "import_order_file",
        "import_order_text",
        "add_vendor_order_shipment",
        "delete_vendor_order_shipment",
    }
)
CATALOG_WRITES = frozenset({"create_product"})
CUSTOMER_WRITES = frozenset(
    {
        "update_customer",
        "create_customer",
        "set_customer_number",
        "create_user",
        "change_customer",
        "create_billing_profile",
        "set_customer_number_for_billing_profile",
        "create_shipping_profile",
        "generate_password_reset_link",
    }
)
WRITE_TOOLS = ORDER_WRITES | CATALOG_WRITES | CUSTOMER_WRITES
PACKAGES = {
    "none": frozenset(),
    "readonly": READ_TOOLS,
    "orders": READ_TOOLS | ORDER_WRITES,
    "catalog": frozenset({"search_products", "get_product"}) | CATALOG_WRITES,
    "customers": frozenset({"list_customers", "get_customer", "list_users", "get_user"})
    | CUSTOMER_WRITES,
    "full": READ_TOOLS | WRITE_TOOLS,
}


@dataclass(frozen=True)
class ToolPolicy:
    package: str = "readonly"
    allow_writes: bool = False
    disabled_tools: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.package not in PACKAGES:
            raise ValueError("Tuntematon MCP_TOOL_PACKAGE. Sallitut: " + ", ".join(PACKAGES))
        if self.disabled_tools - (READ_TOOLS | WRITE_TOOLS | {"list_tool_packages"}):
            raise ValueError("MCP_DISABLED_TOOLS sisältää tuntemattoman työkalun.")

    @property
    def enabled_tools(self) -> frozenset[str]:
        introspection = {"list_tool_packages"} if self.package != "none" else set()
        return (PACKAGES[self.package] | introspection) - self.disabled_tools

    def require(self, name: str, *, execute_write: bool = False) -> None:
        if name not in self.enabled_tools:
            raise ValueError("Työkalu ei ole käytössä palvelimen työkalupaketissa.")
        if execute_write and not self.allow_writes:
            raise ValueError(
                "Kirjoitukset on estetty: WEBMERCS_ALLOW_WRITES=false. Käytä esikatselua."
            )
