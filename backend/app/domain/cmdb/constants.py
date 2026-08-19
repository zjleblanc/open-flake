"""CMDB class hierarchy constants."""

LOGICAL_ROOT = "cmdb"
CMDB_ROOT = "cmdb_ci"

# Fields stored as typed SQL columns on cmdb_ci (query / inventory priority).
PROMOTED_COLUMNS = frozenset(
    {
        "name",
        "host_name",
        "fqdn",
        "short_description",
        "asset_tag",
        "serial_number",
        "install_status",
        "operational_status",
        "classification",
        "environment",
        "ip_address",
        "mac_address",
        "vendor",
        "os",
        "os_version",
        "category",
        "assigned_to",
    }
)

# System / audit fields always allowed on write regardless of class schema.
SYSTEM_FIELDS = frozenset(
    {
        "sys_id",
        "sys_class_name",
        "sys_class_path",
        "sys_created_on",
        "sys_updated_on",
        "sys_created_by",
        "sys_updated_by",
        "sys_mod_count",
        "owner",
        "owner_group",
        "attributes",
    }
)

# Lab seed classes not covered by the shipped base hierarchy or an extra-dir
# export — registered directly under cmdb_ci. Currently empty: the one
# former entry, cmdb_ci_ip_firewall, is now defined properly in the base
# hierarchy (backend/tools/cmdb_base_hierarchy.yaml, under cmdb_ci_netgear).
LAB_CLASS_PARENTS: dict[str, str] = {}
