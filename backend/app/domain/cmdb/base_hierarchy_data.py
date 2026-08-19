"""Default CMDB class hierarchy, shipped with every backend image.

GENERATED FILE -- DO NOT EDIT BY HAND.

Source of truth: `backend/tools/cmdb_base_hierarchy.yaml`.
Regenerate with: `make generate-cmdb-hierarchy`
(or: `python backend/tools/generate_base_hierarchy.py` then `ruff format` it).

Each entry has the same shape as a `docs/class-hierarchy/*.json` export
(`target_table` / `inheritance_path` / `fields`, plus an optional `label`
for the target class itself) that
`app.domain.cmdb.importer._import_export()` already knows how to consume --
this module just supplies them as a Python literal instead of files read off
disk, so the base hierarchy needs no data files shipped in the image.
"""

from __future__ import annotations

from typing import Any

BASE_HIERARCHY: list[dict[str, Any]] = [
    {
        "target_table": "cmdb_ci_hardware",
        "inheritance_path": ["cmdb", "cmdb_ci", "cmdb_ci_hardware"],
        "label": "Hardware",
        "fields": [],
    },
    {
        "target_table": "cmdb_ci_computer",
        "inheritance_path": ["cmdb", "cmdb_ci", "cmdb_ci_hardware", "cmdb_ci_computer"],
        "label": "Computer",
        "fields": [],
    },
    {
        "target_table": "cmdb_ci_server",
        "inheritance_path": [
            "cmdb",
            "cmdb_ci",
            "cmdb_ci_hardware",
            "cmdb_ci_computer",
            "cmdb_ci_server",
        ],
        "label": "Server",
        "fields": [
            {
                "name": "host_name",
                "label": "Host Name",
                "type": "string",
                "source_table": "cmdb_ci_server",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_linux_server",
        "inheritance_path": [
            "cmdb",
            "cmdb_ci",
            "cmdb_ci_hardware",
            "cmdb_ci_computer",
            "cmdb_ci_server",
            "cmdb_ci_linux_server",
        ],
        "label": "Linux Server",
        "fields": [
            {
                "name": "kernel_release",
                "label": "Kernel Release",
                "type": "string",
                "source_table": "cmdb_ci_linux_server",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_unix_server",
        "inheritance_path": [
            "cmdb",
            "cmdb_ci",
            "cmdb_ci_hardware",
            "cmdb_ci_computer",
            "cmdb_ci_server",
            "cmdb_ci_unix_server",
        ],
        "label": "UNIX Server",
        "fields": [
            {
                "name": "kernel_release",
                "label": "Kernel Release",
                "type": "string",
                "source_table": "cmdb_ci_unix_server",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_win_server",
        "inheritance_path": [
            "cmdb",
            "cmdb_ci",
            "cmdb_ci_hardware",
            "cmdb_ci_computer",
            "cmdb_ci_server",
            "cmdb_ci_win_server",
        ],
        "label": "Windows Server",
        "fields": [
            {
                "name": "domain",
                "label": "Domain",
                "type": "string",
                "source_table": "cmdb_ci_win_server",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_storage_device",
        "inheritance_path": ["cmdb", "cmdb_ci", "cmdb_ci_hardware", "cmdb_ci_storage_device"],
        "label": "Storage Device",
        "fields": [],
    },
    {
        "target_table": "cmdb_ci_storage_server",
        "inheritance_path": [
            "cmdb",
            "cmdb_ci",
            "cmdb_ci_hardware",
            "cmdb_ci_storage_device",
            "cmdb_ci_storage_server",
        ],
        "label": "Storage Server",
        "fields": [
            {
                "name": "raid_type",
                "label": "RAID Type",
                "type": "string",
                "source_table": "cmdb_ci_storage_server",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_peripheral",
        "inheritance_path": ["cmdb", "cmdb_ci", "cmdb_ci_hardware", "cmdb_ci_peripheral"],
        "label": "Peripheral",
        "fields": [],
    },
    {
        "target_table": "cmdb_ci_printer",
        "inheritance_path": [
            "cmdb",
            "cmdb_ci",
            "cmdb_ci_hardware",
            "cmdb_ci_peripheral",
            "cmdb_ci_printer",
        ],
        "label": "Printer",
        "fields": [
            {
                "name": "page_count",
                "label": "Page Count",
                "type": "integer",
                "source_table": "cmdb_ci_printer",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_netgear",
        "inheritance_path": ["cmdb", "cmdb_ci", "cmdb_ci_hardware", "cmdb_ci_netgear"],
        "label": "Networking Gear",
        "fields": [],
    },
    {
        "target_table": "cmdb_ci_router",
        "inheritance_path": [
            "cmdb",
            "cmdb_ci",
            "cmdb_ci_hardware",
            "cmdb_ci_netgear",
            "cmdb_ci_router",
        ],
        "label": "Router",
        "fields": [
            {
                "name": "port_count",
                "label": "Port Count",
                "type": "integer",
                "source_table": "cmdb_ci_router",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_switch",
        "inheritance_path": [
            "cmdb",
            "cmdb_ci",
            "cmdb_ci_hardware",
            "cmdb_ci_netgear",
            "cmdb_ci_switch",
        ],
        "label": "Switch",
        "fields": [
            {
                "name": "port_count",
                "label": "Port Count",
                "type": "integer",
                "source_table": "cmdb_ci_switch",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_ip_firewall",
        "inheritance_path": [
            "cmdb",
            "cmdb_ci",
            "cmdb_ci_hardware",
            "cmdb_ci_netgear",
            "cmdb_ci_ip_firewall",
        ],
        "label": "Firewall",
        "fields": [
            {
                "name": "throughput_mbps",
                "label": "Throughput (Mbps)",
                "type": "integer",
                "source_table": "cmdb_ci_ip_firewall",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_lb",
        "inheritance_path": [
            "cmdb",
            "cmdb_ci",
            "cmdb_ci_hardware",
            "cmdb_ci_netgear",
            "cmdb_ci_lb",
        ],
        "label": "Load Balancer",
        "fields": [
            {
                "name": "algorithm",
                "label": "Algorithm",
                "type": "string",
                "source_table": "cmdb_ci_lb",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_vm_object",
        "inheritance_path": ["cmdb", "cmdb_ci", "cmdb_ci_vm_object"],
        "label": "Virtualization Object",
        "fields": [],
    },
    {
        "target_table": "cmdb_ci_vm_instance",
        "inheritance_path": ["cmdb", "cmdb_ci", "cmdb_ci_vm_object", "cmdb_ci_vm_instance"],
        "label": "Virtual Machine Instance",
        "fields": [
            {
                "name": "hypervisor",
                "label": "Hypervisor",
                "type": "string",
                "source_table": "cmdb_ci_vm_instance",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_database",
        "inheritance_path": ["cmdb", "cmdb_ci", "cmdb_ci_database"],
        "label": "Database",
        "fields": [],
    },
    {
        "target_table": "cmdb_ci_db_mysql_instance",
        "inheritance_path": ["cmdb", "cmdb_ci", "cmdb_ci_database", "cmdb_ci_db_mysql_instance"],
        "label": "MySQL Instance",
        "fields": [
            {
                "name": "version",
                "label": "Version",
                "type": "string",
                "source_table": "cmdb_ci_db_mysql_instance",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_db_ora_instance",
        "inheritance_path": ["cmdb", "cmdb_ci", "cmdb_ci_database", "cmdb_ci_db_ora_instance"],
        "label": "Oracle Instance",
        "fields": [
            {
                "name": "sid",
                "label": "SID",
                "type": "string",
                "source_table": "cmdb_ci_db_ora_instance",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_db_postgresql_instance",
        "inheritance_path": [
            "cmdb",
            "cmdb_ci",
            "cmdb_ci_database",
            "cmdb_ci_db_postgresql_instance",
        ],
        "label": "PostgreSQL Instance",
        "fields": [
            {
                "name": "version",
                "label": "Version",
                "type": "string",
                "source_table": "cmdb_ci_db_postgresql_instance",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_appl",
        "inheritance_path": ["cmdb", "cmdb_ci", "cmdb_ci_appl"],
        "label": "Application",
        "fields": [
            {
                "name": "version",
                "label": "Version",
                "type": "string",
                "source_table": "cmdb_ci_appl",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_service",
        "inheritance_path": ["cmdb", "cmdb_ci", "cmdb_ci_service"],
        "label": "Business Service",
        "fields": [],
    },
    {
        "target_table": "cmdb_ci_cloud_service",
        "inheritance_path": ["cmdb", "cmdb_ci", "cmdb_ci_cloud_service"],
        "label": "Cloud Service",
        "fields": [],
    },
    {
        "target_table": "cmdb_ci_cloud_service_account",
        "inheritance_path": [
            "cmdb",
            "cmdb_ci",
            "cmdb_ci_cloud_service",
            "cmdb_ci_cloud_service_account",
        ],
        "label": "Cloud Service Account",
        "fields": [
            {
                "name": "provider",
                "label": "Provider",
                "type": "string",
                "source_table": "cmdb_ci_cloud_service_account",
            }
        ],
    },
    {
        "target_table": "cmdb_ci_cloud_resource",
        "inheritance_path": ["cmdb", "cmdb_ci", "cmdb_ci_cloud_service", "cmdb_ci_cloud_resource"],
        "label": "Cloud Resource",
        "fields": [
            {
                "name": "resource_type",
                "label": "Resource Type",
                "type": "string",
                "source_table": "cmdb_ci_cloud_resource",
            }
        ],
    },
]
