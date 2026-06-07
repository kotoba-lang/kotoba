"""Domain adapters for supplychain.etzhayyim.com — cleaning robot manufacturing.

Normalizes robotics and automotive material tables into the shared
jukyu SoS tables (domain='cleaning_robot') so the Pregel graph can run
the same pressure-propagation algorithm across the cleaning robot
upstream material graph.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


def normalize_cleaning_robot() -> dict[str, Any]:
    """Normalize the cleaning-robot manufacturing supply graph into Jukyu SoS tables.

    Sources:
      vertex_automotive_material_requirement  → material supply nodes
      vertex_robotics_product_package         → assembly nodes
      edge_automotive_material_supplied_by    → supplier nodes + supplier→material edges
      edge_automotive_package_requires_material → material→package edges

    Idempotent: handled by kotoba_datomic.insert_row upsert semantics.
    """
    stats: dict[str, Any] = {"ok": True, "domain": "cleaning_robot"}
    kotoba = get_kotoba_client()

    # ── Idempotent inserts handled by insert_row upsert semantics ───────────

    # ── Supply nodes: material requirements ──────────────────────────────────
    material_nodes_count = 0
    material_requirements = kotoba.select_where(
        "vertex_automotive_material_requirement",
        "status",
        "deleted",
        exclude_pattern=True,
    )
    # R0: Filtering for NULL status in Python, as select_where does not support IS NULL.
    # The original query was "WHERE status IS NULL OR status <> 'deleted'".
    # Our select_where excludes 'deleted', so we only need to handle IS NULL.
    material_requirements = [
        r for r in material_requirements if r.get("status") is None or r.get("status") != "deleted"
    ]

    for row in material_requirements:
        jukyu_supply_node_row = {
            "vertex_id": "jukyu-node:cleaning_robot:material:" + row["vertex_id"],
            "created_date": datetime.now(timezone.utc).date().isoformat(),
            "sensitivity_ord": row.get("sensitivity_ord") or 1,
            "owner_did": row.get("owner_did") or "did:web:supplychain.etzhayyim.com",
            "repo": row.get("repo") or "did:web:supplychain.etzhayyim.com",
            "domain": "cleaning_robot",
            "node_code": row["material_id"],
            "node_kind": row.get("material_kind") or "material",
            "display_name": row.get("specification") or row["material_id"],
            "country_code": row.get("country_of_origin") or "ZZ",
            "operator_did": None,
            "product_code": row.get("material_kind") or "cleaning_robot_material",
            "product_family": "cleaning_robot_material",
            "capacity_unit": "units",
            "demand_capacity": row.get("quantity_per_vehicle") or 1.0,
            "status": row.get("status") or "active",
            "source_table": "vertex_automotive_material_requirement",
            "source_vertex_id": row["vertex_id"],
            "collection": "com.etzhayyim.apps.supplychain.supplyNode",
            "actor_did": "did:web:supplychain.etzhayyim.com",
            "org_did": "did:web:etzhayyim.com",
        }
        kotoba.insert_row("vertex_jukyu_supply_node", jukyu_supply_node_row)
        material_nodes_count += 1
    stats["materialNodes"] = material_nodes_count

    # ── Supply nodes: robotics product packages (assembly nodes) ─────────────
    assembly_nodes_count = 0
    product_packages = kotoba.select_where(
        "vertex_robotics_product_package",
        "readiness_status",
        "cancelled",
        exclude_pattern=True,
    )
    # R0: Filtering for NULL readiness_status in Python.
    product_packages = [
        r for r in product_packages if r.get("readiness_status") is None or r.get("readiness_status") != "cancelled"
    ]

    for row in product_packages:
        jukyu_supply_node_row = {
            "vertex_id": "jukyu-node:cleaning_robot:package:" + row["vertex_id"],
            "created_date": datetime.now(timezone.utc).date().isoformat(),
            "sensitivity_ord": row.get("sensitivity_ord") or 1,
            "owner_did": row.get("owner_did") or "did:web:supplychain.etzhayyim.com",
            "repo": row.get("repo") or "did:web:supplychain.etzhayyim.com",
            "domain": "cleaning_robot",
            "node_code": row["package_id"],
            "node_kind": row.get("asset_kind") or "assembly",
            "display_name": row.get("package_id") or row["vertex_id"],
            "country_code": row.get("target_supplier_region") or "JP",
            "operator_did": None,
            "product_code": row.get("asset_kind") or "cleaning_robot",
            "product_family": "cleaning_robot_assembly",
            "capacity_unit": "units",
            "status": row.get("readiness_status") or "active",
            "source_table": "vertex_robotics_product_package",
            "source_vertex_id": row["vertex_id"],
            "collection": "com.etzhayyim.apps.supplychain.supplyNode",
            "actor_did": "did:web:supplychain.etzhayyim.com",
            "org_did": "did:web:etzhayyim.com",
        }
        kotoba.insert_row("vertex_jukyu_supply_node", jukyu_supply_node_row)
        assembly_nodes_count += 1
    stats["assemblyNodes"] = assembly_nodes_count

    # ── Supply nodes: unique suppliers (from edge_automotive_material_supplied_by) ──
    # R0: Replicating CTE, MIN/MAX aggregation, and GROUP BY in Python.
    supplier_nodes_count = 0
    all_material_supplied_by_edges = kotoba.select_where(
        "edge_automotive_material_supplied_by", "supplier_lei", None, exclude_pattern=True
    )
    
    unique_suppliers_map = {}
    for edge in all_material_supplied_by_edges:
        supplier_lei = edge.get("supplier_lei")
        if supplier_lei:
            if supplier_lei not in unique_suppliers_map:
                unique_suppliers_map[supplier_lei] = {
                    "supplier_lei": supplier_lei,
                    "edge_id": edge["edge_id"],  # MIN(edge_id) is handled by first seen
                    "is_qualified": 0,
                }
            
            # MAX(CASE WHEN qualification_status = 'qualified' THEN 1 ELSE 0 END)
            if edge.get("qualification_status") == "qualified":
                unique_suppliers_map[supplier_lei]["is_qualified"] = 1

    for s in unique_suppliers_map.values():
        jukyu_supply_node_row = {
            "vertex_id": "jukyu-node:cleaning_robot:supplier:" + s["supplier_lei"],
            "created_date": datetime.now(timezone.utc).date().isoformat(),
            "sensitivity_ord": 1,
            "owner_did": "did:web:supplychain.etzhayyim.com",
            "repo": "did:web:supplychain.etzhayyim.com",
            "domain": "cleaning_robot",
            "node_code": s["supplier_lei"],
            "node_kind": "supplier",
            "display_name": s["supplier_lei"],
            "country_code": "ZZ",
            "operator_did": "did:web:lei:" + s["supplier_lei"],
            "product_code": "cleaning_robot_material",
            "product_family": "cleaning_robot_supplier",
            "capacity_unit": "units",
            "status": "active" if s["is_qualified"] == 1 else "inactive",
            "source_table": "edge_automotive_material_supplied_by",
            "source_vertex_id": s["edge_id"],
            "collection": "com.etzhayyim.apps.supplychain.supplyNode",
            "actor_did": "did:web:supplychain.etzhayyim.com",
            "org_did": "did:web:etzhayyim.com",
        }
        kotoba.insert_row("vertex_jukyu_supply_node", jukyu_supply_node_row)
        supplier_nodes_count += 1
    stats["supplierNodes"] = supplier_nodes_count

    # ── Supply dependencies: supplier → material (supplier provides material) ─
    supplier_material_deps_count = 0
    material_supplied_by_edges = kotoba.select_where(
        "edge_automotive_material_supplied_by",
        "qualification_status",
        "disqualified",
        exclude_pattern=True,
    )
    # R0: Filtering for NULL qualification_status in Python.
    material_supplied_by_edges = [
        e for e in material_supplied_by_edges if e.get("qualification_status") is None or e.get("qualification_status") != "disqualified"
    ]

    jukyu_supplier_nodes = kotoba.select_where(
        "vertex_jukyu_supply_node", "domain", "cleaning_robot"
    )
    sup_node_map = {
        node["node_code"]: node
        for node in jukyu_supplier_nodes
        if node["source_table"] == "edge_automotive_material_supplied_by"
    }
    mat_node_map = {
        node["node_code"]: node
        for node in jukyu_supplier_nodes
        if node["source_table"] == "vertex_automotive_material_requirement"
    }

    for e in material_supplied_by_edges:
        sup_node = sup_node_map.get(e["supplier_lei"])
        mat_node = mat_node_map.get(e["material_id"])

        if sup_node and mat_node:
            qualification_status = e.get("qualification_status")
            dependency_weight = 0.2
            if qualification_status == "qualified":
                dependency_weight = 1.0
            elif qualification_status == "conditional":
                dependency_weight = 0.5

            status = "active"
            if qualification_status == "disqualified":
                status = "inactive"

            edge_jukyu_supply_dependency_row = {
                "edge_id": "jukyu-edge:cleaning_robot:supplier:" + e["edge_id"],
                "src_vid": sup_node["vertex_id"],
                "dst_vid": mat_node["vertex_id"],
                "created_date": datetime.now(timezone.utc).date().isoformat(),
                "sensitivity_ord": 1,
                "owner_did": "did:web:supplychain.etzhayyim.com",
                "domain": "cleaning_robot",
                "relationship": "material_supply",
                "product_code": e["material_id"],
                "product_family": "cleaning_robot_material",
                "dependency_weight": dependency_weight,
                "confidence": 0.70,
                "status": status,
            }
            kotoba.insert_row("edge_jukyu_supply_dependency", edge_jukyu_supply_dependency_row)
            supplier_material_deps_count += 1
    stats["supplierMaterialDeps"] = supplier_material_deps_count

    # ── Supply dependencies: material → package (package requires material) ──
    package_material_deps_count = 0
    package_requires_material_edges = kotoba.select_where(
        "edge_automotive_package_requires_material", "edge_id", None, exclude_pattern=False # No WHERE clause in SQL
    )

    pkg_node_map = {
        node["node_code"]: node
        for node in jukyu_supplier_nodes # jukyu_supplier_nodes is already fetched
        if node["source_table"] == "vertex_robotics_product_package"
    }

    for e in package_requires_material_edges:
        mat_node = mat_node_map.get(e["material_id"]) # mat_node_map is already available
        pkg_node = pkg_node_map.get(e["package_id"])

        if mat_node and pkg_node:
            requirement_kind = e.get("requirement_kind")
            dependency_weight = 0.7
            if requirement_kind == "critical":
                dependency_weight = 1.0
            elif requirement_kind == "optional":
                dependency_weight = 0.3

            edge_jukyu_supply_dependency_row = {
                "edge_id": "jukyu-edge:cleaning_robot:pkg-mat:" + e["edge_id"],
                "src_vid": mat_node["vertex_id"],
                "dst_vid": pkg_node["vertex_id"],
                "created_date": datetime.now(timezone.utc).date().isoformat(),
                "sensitivity_ord": 1,
                "owner_did": "did:web:supplychain.etzhayyim.com",
                "domain": "cleaning_robot",
                "relationship": "material_required",
                "product_code": e["material_id"],
                "product_family": "cleaning_robot_material",
                "dependency_weight": dependency_weight,
                "confidence": 0.65,
                "status": "active",
            }
            kotoba.insert_row("edge_jukyu_supply_dependency", edge_jukyu_supply_dependency_row)
            package_material_deps_count += 1
    stats["packageMaterialDeps"] = package_material_deps_count

    # ── Balance observations: demand = material req count, supply = qualified suppliers ──
    # R0: Replicating LEFT JOIN, GROUP BY, COUNT(DISTINCT) in Python.
    balance_observations_count = 0
    material_requirements_for_balance = kotoba.select_where(
        "vertex_automotive_material_requirement",
        "status",
        "deleted",
        exclude_pattern=True,
    )
    # R0: Filtering for NULL status in Python.
    material_requirements_for_balance = [
        m for m in material_requirements_for_balance if m.get("status") is None or m.get("status") != "deleted"
    ]

    material_supplied_by_all = kotoba.select_where(
        "edge_automotive_material_supplied_by", "edge_id", None, exclude_pattern=False
    )
    
    # Grouping logic
    balance_groups = {} # Key: (country_code, material_kind)

    for m in material_requirements_for_balance:
        country_code = m.get("country_of_origin") or "ZZ"
        material_kind = m.get("material_kind") or "unknown"
        group_key = (country_code, material_kind)

        if group_key not in balance_groups:
            balance_groups[group_key] = {
                "material_requirements": [],
                "supplier_leis": set(),
            }
        
        balance_groups[group_key]["material_requirements"].append(m)
        
        # Simulate LEFT JOIN conditions
        for ms in material_supplied_by_all:
            if ms.get("material_id") == m["material_id"] and \
               (ms.get("qualification_status") is None or ms.get("qualification_status") == "qualified"):
                if ms.get("supplier_lei"):
                    balance_groups[group_key]["supplier_leis"].add(ms["supplier_lei"])

    for group_key, data in balance_groups.items():
        country_code, material_kind = group_key
        supply_quantity = float(len(data["supplier_leis"]))
        demand_quantity = float(len(data["material_requirements"]))
        balance_quantity = supply_quantity - demand_quantity

        obs_id_suffix = f"{country_code}:{material_kind}"
        
        vertex_jukyu_balance_observation_row = {
            "vertex_id": f"jukyu-obs:cleaning_robot:{obs_id_suffix}",
            "created_date": datetime.now(timezone.utc).date().isoformat(),
            "sensitivity_ord": 1,
            "owner_did": "did:web:supplychain.etzhayyim.com",
            "repo": "did:web:supplychain.etzhayyim.com",
            "observation_id": f"cleaning_robot_adapter:{obs_id_suffix}",
            "domain": "cleaning_robot",
            "country_code": country_code,
            "product_code": material_kind,
            "product_family": "cleaning_robot_material",
            "supply_quantity": supply_quantity,
            "demand_quantity": demand_quantity,
            "balance_quantity": balance_quantity,
            "quantity_unit": "units",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "source_kind": "cleaning_robot_adapter",
            "confidence": 0.60,
            "status": "active",
            "collection": "com.etzhayyim.apps.supplychain.balanceObservation",
            "actor_did": "did:web:supplychain.etzhayyim.com",
            "org_did": "did:web:etzhayyim.com",
        }
        kotoba.insert_row("vertex_jukyu_balance_observation", vertex_jukyu_balance_observation_row)
        balance_observations_count += 1
    stats["balanceObservations"] = balance_observations_count

    return stats
