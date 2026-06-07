"""Domain adapters for Jukyu global supply-demand SoS."""

from __future__ import annotations

from typing import Any

from kotodama.db_sync import execute, fetch_one, fetch_all


def normalize_naphtha() -> dict[str, Any]:
    """Normalize the naphtha supply-chain graph into Jukyu SoS tables.

    The adapter is idempotent: rows sourced from naphtha are deleted and
    reinserted so the materialized views converge on the latest source graph.
    """

    stats: dict[str, Any] = {"ok": True, "domain": "naphtha"}

    execute("DELETE FROM edge_jukyu_company_operates_node WHERE edge_id LIKE %s", ("jukyu-operates:naphtha:%",))
    execute("DELETE FROM edge_jukyu_supply_dependency WHERE edge_id LIKE %s", ("jukyu-edge:naphtha:%",))
    execute("DELETE FROM vertex_jukyu_company_exposure WHERE run_id = %s", ("jukyu.adapter.naphtha.latest",))
    execute("DELETE FROM vertex_jukyu_balance_observation WHERE source_kind = %s", ("naphtha_adapter",))
    execute("DELETE FROM vertex_jukyu_supply_node WHERE source_table = %s", ("vertex_naphtha_market_node",))

    stats["supplyNodes"] = execute(
        """
        INSERT INTO vertex_jukyu_supply_node
          (vertex_id, created_date, sensitivity_ord, owner_did, repo,
           domain, node_code, node_kind, display_name, country_code, region_code,
           locode, operator_did, product_code, product_family, capacity_unit,
           supply_capacity, demand_capacity, status, source_table,
           source_vertex_id, collection, actor_did, org_did)
        SELECT
          'jukyu-node:naphtha:' || vertex_id,
          created_date,
          COALESCE(sensitivity_ord, 1),
          owner_did,
          repo,
          'naphtha',
          node_code,
          node_kind,
          display_name,
          country_code,
          CAST(NULL AS VARCHAR),
          locode,
          operator_did,
          COALESCE(product_code, 'NAPH'),
          'petrochemical_feedstock',
          'tonnes_day',
          CASE
            WHEN node_kind IN ('refinery', 'splitter', 'export_terminal') THEN capacity_tonnes_day
            ELSE NULL
          END::DOUBLE PRECISION,
          CASE
            WHEN node_kind IN ('steam_cracker', 'petrochemical_plant', 'import_terminal') THEN capacity_tonnes_day
            ELSE NULL
          END::DOUBLE PRECISION,
          status,
          'vertex_naphtha_market_node',
          vertex_id,
          'com.etzhayyim.apps.jukyu.supplyNode',
          'did:web:jukyu.etzhayyim.com',
          org_did
        FROM vertex_naphtha_market_node
        WHERE status IS NULL OR status <> 'deleted'
        """
    )

    stats["supplyDependencies"] = execute(
        """
        INSERT INTO edge_jukyu_supply_dependency
          (edge_id, src_vid, dst_vid, created_date, sensitivity_ord, owner_did,
           domain, relationship, product_code, product_family,
           capacity_quantity, quantity_unit, dependency_weight,
           confidence, status)
        SELECT
          'jukyu-edge:naphtha:' || edge_id,
          'jukyu-node:naphtha:' || src_vid,
          'jukyu-node:naphtha:' || dst_vid,
          created_date,
          sensitivity_ord,
          owner_did,
          'naphtha',
          relationship,
          COALESCE(grade_code, 'NAPH'),
          'petrochemical_feedstock',
          capacity_tonnes_day,
          'tonnes_day',
          CASE
            WHEN COALESCE(capacity_tonnes_day, 0.0) <= 0.0 THEN 0.0
            WHEN capacity_tonnes_day >= 6000.0 THEN 1.0
            ELSE capacity_tonnes_day / 6000.0
          END,
          0.72,
          status
        FROM edge_naphtha_supply_link
        WHERE status IS NULL OR status <> 'deleted'
        """
    )

    stats["companyOperateEdges"] = execute(
        """
        INSERT INTO edge_jukyu_company_operates_node
          (edge_id, src_vid, dst_vid, created_date, sensitivity_ord, owner_did,
           role, ownership_pct, confidence, status)
        SELECT
          'jukyu-operates:naphtha:' || operator_did || ':' || vertex_id,
          operator_did,
          'jukyu-node:naphtha:' || vertex_id,
          created_date,
          sensitivity_ord,
          owner_did,
          'operator',
          CAST(NULL AS DOUBLE PRECISION),
          0.72,
          status
        FROM vertex_naphtha_market_node
        WHERE operator_did IS NOT NULL
          AND operator_did <> ''
          AND (status IS NULL OR status <> 'deleted')
        """
    )

    stats["balanceObservations"] = execute(
        """
        INSERT INTO vertex_jukyu_balance_observation
          (vertex_id, created_date, sensitivity_ord, owner_did, repo,
           observation_id, domain, country_code, product_code, product_family,
           supply_quantity, demand_quantity, balance_quantity, quantity_unit,
           observed_at, source_kind, confidence, status, collection, actor_did, org_did)
        SELECT
          'jukyu-balance:naphtha:' || COALESCE(country_code, 'ZZ') || ':latest',
          CAST(NOW() AS DATE),
          1,
          'did:web:jukyu.etzhayyim.com',
          'did:web:jukyu.etzhayyim.com',
          'naphtha:' || COALESCE(country_code, 'ZZ') || ':latest',
          'naphtha',
          country_code,
          'NAPH',
          'petrochemical_feedstock',
          supply_capacity_tonnes_day,
          demand_capacity_tonnes_day,
          balance_tonnes_day,
          'tonnes_day',
          NOW()::varchar,
          'naphtha_adapter',
          0.72,
          'active',
          'com.etzhayyim.apps.jukyu.balanceObservation',
          'did:web:jukyu.etzhayyim.com',
          'did:web:etzhayyim.com'
        FROM mv_naphtha_country_balance
        """
    )

    stats["companyExposures"] = execute(
        """
        INSERT INTO vertex_jukyu_company_exposure
          (vertex_id, created_date, sensitivity_ord, owner_did, repo,
           exposure_id, run_id, company_did, company_name, domain, country_code,
           product_code, product_family, supply_pressure, demand_pressure,
           downstream_pressure, structural_pressure, risk_score, confidence,
           evidence_json, recommended_action, status, collection, actor_did, org_did)
        SELECT
          'jukyu-exposure:naphtha:' || n.operator_did || ':' || COALESCE(n.country_code, 'ZZ'),
          CAST(NOW() AS DATE),
          1,
          'did:web:jukyu.etzhayyim.com',
          'did:web:jukyu.etzhayyim.com',
          'naphtha:' || n.operator_did || ':' || COALESCE(n.country_code, 'ZZ'),
          'jukyu.adapter.naphtha.latest',
          n.operator_did,
          n.display_name,
          'naphtha',
          n.country_code,
          COALESCE(n.product_code, 'NAPH'),
          'petrochemical_feedstock',
          CASE
            WHEN b.balance_tonnes_day < 0.0 THEN LEAST(1.0, ABS(b.balance_tonnes_day) / GREATEST(b.demand_capacity_tonnes_day, 1.0))
            ELSE 0.0
          END,
          CASE
            WHEN n.node_kind IN ('steam_cracker', 'petrochemical_plant', 'import_terminal') THEN 0.85
            ELSE 0.25
          END,
          CASE
            WHEN b.balance_tonnes_day < 0.0 THEN 0.65
            ELSE 0.15
          END,
          CASE
            WHEN n.node_kind IN ('steam_cracker', 'petrochemical_plant') THEN 0.55
            ELSE 0.25
          END,
          CASE
            WHEN b.balance_tonnes_day < 0.0 AND n.node_kind IN ('steam_cracker', 'petrochemical_plant', 'import_terminal')
              THEN LEAST(0.95, 0.55 + 0.35 * ABS(b.balance_tonnes_day) / GREATEST(b.demand_capacity_tonnes_day, 1.0))
            WHEN b.balance_tonnes_day < 0.0
              THEN 0.58
            ELSE 0.25
          END,
          0.72,
          '[{"source":"mv_naphtha_country_balance","reason":"country balance normalized into Jukyu SoS"}]',
          'Evaluate alternate naphtha supply routes, term coverage, cracker run-rate flexibility, and inventory buffer.',
          'active',
          'com.etzhayyim.apps.jukyu.companyExposure',
          'did:web:jukyu.etzhayyim.com',
          COALESCE(n.org_did, 'did:web:etzhayyim.com')
        FROM vertex_naphtha_market_node n
        JOIN mv_naphtha_country_balance b ON b.country_code = n.country_code
        WHERE n.operator_did IS NOT NULL
          AND n.operator_did <> ''
          AND (n.status IS NULL OR n.status <> 'deleted')
        """
    )

    for key, table in (
        ("jukyuSupplyNodesTotal", "vertex_jukyu_supply_node"),
        ("jukyuBalanceRowsTotal", "vertex_jukyu_balance_observation"),
        ("jukyuExposureRowsTotal", "vertex_jukyu_company_exposure"),
    ):
        row = fetch_one(f"SELECT COUNT(*) FROM {table} WHERE domain = %s", ("naphtha",))
        stats[key] = int(row[0]) if row else 0

    return stats


def normalize_crude_oil() -> dict[str, Any]:
    """Normalize crude oil supply-chain graph into Jukyu SoS tables.

    Reads from: vertex_oil_field, vertex_oil_terminal, vertex_refinery,
                edge_feeds, edge_operates.
    The adapter is idempotent: rows sourced from crude_oil are deleted and
    reinserted so materialized views converge on the latest source graph.
    """

    stats: dict[str, Any] = {"ok": True, "domain": "crude_oil"}

    execute("DELETE FROM edge_jukyu_company_operates_node WHERE edge_id LIKE %s", ("jukyu-operates:crude_oil:%",))
    execute("DELETE FROM edge_jukyu_supply_dependency WHERE edge_id LIKE %s", ("jukyu-edge:crude_oil:%",))
    execute("DELETE FROM vertex_jukyu_company_exposure WHERE run_id = %s", ("jukyu.adapter.crude_oil.latest",))
    execute("DELETE FROM vertex_jukyu_balance_observation WHERE source_kind = %s", ("crude_oil_adapter",))
    execute("DELETE FROM vertex_jukyu_supply_node WHERE source_table = %s", ("vertex_oil_field",))
    execute("DELETE FROM vertex_jukyu_supply_node WHERE source_table = %s", ("vertex_oil_terminal",))
    execute("DELETE FROM vertex_jukyu_supply_node WHERE source_table = %s", ("vertex_refinery",))

    # Supply nodes: oil fields (upstream supply sources, no capacity data in schema)
    field_rows = execute(
        """
        INSERT INTO vertex_jukyu_supply_node
          (vertex_id, created_date, sensitivity_ord, owner_did, repo,
           domain, node_code, node_kind, display_name, country_code, region_code,
           locode, operator_did, product_code, product_family, capacity_unit,
           supply_capacity, demand_capacity, status, source_table,
           source_vertex_id, collection, actor_did, org_did)
        SELECT
          'jukyu-node:crude_oil:' || vertex_id,
          created_date,
          COALESCE(sensitivity_ord, 1),
          owner_did,
          repo,
          'crude_oil',
          COALESCE(field_code, vertex_id),
          'oil_field',
          COALESCE(field_code, vertex_id),
          country_code,
          CAST(NULL AS VARCHAR),
          CAST(NULL AS VARCHAR),
          operator_did,
          'CRUD',
          'crude_oil',
          'bpd',
          CAST(NULL AS DOUBLE PRECISION),
          CAST(NULL AS DOUBLE PRECISION),
          status,
          'vertex_oil_field',
          vertex_id,
          'com.etzhayyim.apps.jukyu.supplyNode',
          'did:web:jukyu.etzhayyim.com',
          CAST(NULL AS VARCHAR)
        FROM vertex_oil_field
        WHERE status IS NULL OR status <> 'deleted'
        """
    )

    # Supply nodes: oil terminals (bidirectional export/import nodes)
    terminal_rows = execute(
        """
        INSERT INTO vertex_jukyu_supply_node
          (vertex_id, created_date, sensitivity_ord, owner_did, repo,
           domain, node_code, node_kind, display_name, country_code, region_code,
           locode, operator_did, product_code, product_family, capacity_unit,
           supply_capacity, demand_capacity, status, source_table,
           source_vertex_id, collection, actor_did, org_did)
        SELECT
          'jukyu-node:crude_oil:' || vertex_id,
          created_date,
          COALESCE(sensitivity_ord, 1),
          owner_did,
          repo,
          'crude_oil',
          COALESCE(terminal_code, vertex_id),
          'oil_terminal',
          COALESCE(terminal_code, vertex_id),
          CAST(NULL AS VARCHAR),
          CAST(NULL AS VARCHAR),
          locode,
          operator_did,
          'CRUD',
          'crude_oil',
          'bpd',
          CASE WHEN terminal_type = 'export' THEN storage_capacity::DOUBLE PRECISION ELSE NULL END,
          CASE WHEN terminal_type = 'import' THEN storage_capacity::DOUBLE PRECISION ELSE NULL END,
          status,
          'vertex_oil_terminal',
          vertex_id,
          'com.etzhayyim.apps.jukyu.supplyNode',
          'did:web:jukyu.etzhayyim.com',
          CAST(NULL AS VARCHAR)
        FROM vertex_oil_terminal
        WHERE status IS NULL OR status <> 'deleted'
        """
    )

    # Supply nodes: refineries (downstream demand nodes consuming crude)
    refinery_rows = execute(
        """
        INSERT INTO vertex_jukyu_supply_node
          (vertex_id, created_date, sensitivity_ord, owner_did, repo,
           domain, node_code, node_kind, display_name, country_code, region_code,
           locode, operator_did, product_code, product_family, capacity_unit,
           supply_capacity, demand_capacity, status, source_table,
           source_vertex_id, collection, actor_did, org_did)
        SELECT
          'jukyu-node:crude_oil:' || vertex_id,
          created_date,
          COALESCE(sensitivity_ord, 1),
          owner_did,
          repo,
          'crude_oil',
          COALESCE(refinery_code, vertex_id),
          'refinery',
          COALESCE(refinery_code, vertex_id),
          country_code,
          CAST(NULL AS VARCHAR),
          CAST(NULL AS VARCHAR),
          operator_did,
          'CRUD',
          'crude_oil',
          'bpd',
          CAST(NULL AS DOUBLE PRECISION),
          throughput_bpd::DOUBLE PRECISION,
          status,
          'vertex_refinery',
          vertex_id,
          'com.etzhayyim.apps.jukyu.supplyNode',
          'did:web:jukyu.etzhayyim.com',
          CAST(NULL AS VARCHAR)
        FROM vertex_refinery
        WHERE status IS NULL OR status <> 'deleted'
        """
    )

    stats["supplyNodes"] = (field_rows or 0) + (terminal_rows or 0) + (refinery_rows or 0)

    # Supply dependencies: edge_feeds connecting normalized crude_oil nodes
    stats["supplyDependencies"] = execute(
        """
        INSERT INTO edge_jukyu_supply_dependency
          (edge_id, src_vid, dst_vid, created_date, sensitivity_ord, owner_did,
           domain, relationship, product_code, product_family,
           capacity_quantity, quantity_unit, dependency_weight,
           confidence, status)
        SELECT
          'jukyu-edge:crude_oil:' || f.edge_id,
          jsrc.vertex_id,
          jdst.vertex_id,
          f.created_date,
          COALESCE(f.sensitivity_ord, 1),
          f.owner_did,
          'crude_oil',
          'feeds',
          COALESCE(f.commodity, 'CRUD'),
          'crude_oil',
          f.capacity::DOUBLE PRECISION,
          COALESCE(f.unit, 'bpd'),
          CASE
            WHEN COALESCE(f.capacity, 0) <= 0 THEN 0.0
            WHEN f.capacity >= 1000000 THEN 1.0
            ELSE f.capacity::DOUBLE PRECISION / 1000000.0
          END,
          0.68,
          'active'
        FROM edge_feeds f
        INNER JOIN vertex_jukyu_supply_node jsrc
          ON jsrc.source_vertex_id = f.src_vid AND jsrc.domain = 'crude_oil'
        INNER JOIN vertex_jukyu_supply_node jdst
          ON jdst.source_vertex_id = f.dst_vid AND jdst.domain = 'crude_oil'
        """
    )

    # Company operate edges: edge_operates connecting operators to crude_oil nodes
    stats["companyOperateEdges"] = execute(
        """
        INSERT INTO edge_jukyu_company_operates_node
          (edge_id, src_vid, dst_vid, created_date, sensitivity_ord, owner_did,
           role, ownership_pct, confidence, status)
        SELECT
          'jukyu-operates:crude_oil:' || e.edge_id,
          e.src_vid,
          jsn.vertex_id,
          e.created_date,
          COALESCE(e.sensitivity_ord, 1),
          e.owner_did,
          COALESCE(e.role, 'operator'),
          CAST(NULL AS DOUBLE PRECISION),
          0.68,
          'active'
        FROM edge_operates e
        INNER JOIN vertex_jukyu_supply_node jsn
          ON jsn.source_vertex_id = e.dst_vid AND jsn.domain = 'crude_oil'
        """
    )

    # Balance observations: aggregate refinery demand by country
    # Supply quantity is NULL because oil_field has no capacity column in schema
    stats["balanceObservations"] = execute(
        """
        INSERT INTO vertex_jukyu_balance_observation
          (vertex_id, created_date, sensitivity_ord, owner_did, repo,
           observation_id, domain, country_code, product_code, product_family,
           supply_quantity, demand_quantity, balance_quantity, quantity_unit,
           observed_at, source_kind, confidence, status, collection, actor_did, org_did)
        SELECT
          'jukyu-balance:crude_oil:' || COALESCE(country_code, 'ZZ') || ':latest',
          CAST(NOW() AS DATE),
          1,
          'did:web:jukyu.etzhayyim.com',
          'did:web:jukyu.etzhayyim.com',
          'crude_oil:' || COALESCE(country_code, 'ZZ') || ':latest',
          'crude_oil',
          country_code,
          'CRUD',
          'crude_oil',
          CAST(NULL AS DOUBLE PRECISION),
          SUM(throughput_bpd)::DOUBLE PRECISION,
          -SUM(throughput_bpd)::DOUBLE PRECISION,
          'bpd',
          NOW()::varchar,
          'crude_oil_adapter',
          0.55,
          'active',
          'com.etzhayyim.apps.jukyu.balanceObservation',
          'did:web:jukyu.etzhayyim.com',
          'did:web:etzhayyim.com'
        FROM vertex_refinery
        WHERE (status IS NULL OR status <> 'deleted')
          AND country_code IS NOT NULL
          AND throughput_bpd IS NOT NULL
        GROUP BY country_code
        """
    )

    # Company exposures: operators with refineries (demand-side exposure)
    stats["companyExposures"] = execute(
        """
        INSERT INTO vertex_jukyu_company_exposure
          (vertex_id, created_date, sensitivity_ord, owner_did, repo,
           exposure_id, run_id, company_did, company_name, domain, country_code,
           product_code, product_family, supply_pressure, demand_pressure,
           downstream_pressure, structural_pressure, risk_score, confidence,
           evidence_json, recommended_action, status, collection, actor_did, org_did)
        SELECT
          'jukyu-exposure:crude_oil:' || r.operator_did || ':' || COALESCE(r.country_code, 'ZZ'),
          CAST(NOW() AS DATE),
          1,
          'did:web:jukyu.etzhayyim.com',
          'did:web:jukyu.etzhayyim.com',
          'crude_oil:' || r.operator_did || ':' || COALESCE(r.country_code, 'ZZ'),
          'jukyu.adapter.crude_oil.latest',
          r.operator_did,
          COALESCE(r.refinery_code, r.operator_did),
          'crude_oil',
          r.country_code,
          'CRUD',
          'crude_oil',
          0.60,
          CASE
            WHEN r.throughput_bpd >= 300000 THEN 0.85
            WHEN r.throughput_bpd >= 100000 THEN 0.65
            ELSE 0.45
          END,
          0.50,
          CASE
            WHEN r.complexity_index IS NOT NULL AND r.complexity_index >= 10.0 THEN 0.70
            ELSE 0.40
          END,
          CASE
            WHEN r.throughput_bpd >= 300000 THEN 0.72
            WHEN r.throughput_bpd >= 100000 THEN 0.60
            ELSE 0.45
          END,
          0.55,
          '[{"source":"vertex_refinery","reason":"refinery throughput normalized into Jukyu SoS"}]',
          'Evaluate term crude supply contracts, strategic petroleum reserves, and crude grade flexibility.',
          'active',
          'com.etzhayyim.apps.jukyu.companyExposure',
          'did:web:jukyu.etzhayyim.com',
          'did:web:etzhayyim.com'
        FROM vertex_refinery r
        WHERE r.operator_did IS NOT NULL
          AND r.operator_did <> ''
          AND (r.status IS NULL OR r.status <> 'deleted')
        """
    )

    for key, table in (
        ("jukyuSupplyNodesTotal", "vertex_jukyu_supply_node"),
        ("jukyuBalanceRowsTotal", "vertex_jukyu_balance_observation"),
        ("jukyuExposureRowsTotal", "vertex_jukyu_company_exposure"),
    ):
        row = fetch_one(f"SELECT COUNT(*) FROM {table} WHERE domain = %s", ("crude_oil",))
        stats[key] = int(row[0]) if row else 0

    return stats


def normalize_semiconductor() -> dict[str, Any]:
    """Normalize smartphone SoC/EMS supply chain into Jukyu SoS tables.

    Sources:
      vertex_open_smartphone_soc_design    → foundry (fab) + SoC chip supply nodes
      vertex_open_smartphone_ems_facility  → EMS assembly facility demand nodes
      vertex_open_smartphone_soc_fab_order → balance observations (wafer demand)
      vertex_open_smartphone_bom           → SoC → EMS dependency edges

    Supply chain direction (upstream → downstream):
      foundry (fab) → soc_design → ems_facility

    Domain: semiconductor
    Idempotent: delete-then-insert pattern.
    """
    stats: dict[str, Any] = {"ok": True, "domain": "semiconductor"}

    execute("DELETE FROM edge_jukyu_company_operates_node WHERE edge_id LIKE %s", ("jukyu-operates:semiconductor:%",))
    execute("DELETE FROM edge_jukyu_supply_dependency WHERE edge_id LIKE %s", ("jukyu-edge:semiconductor:%",))
    execute("DELETE FROM vertex_jukyu_company_exposure WHERE run_id = %s", ("jukyu.adapter.semiconductor.latest",))
    execute("DELETE FROM vertex_jukyu_balance_observation WHERE source_kind = %s", ("semiconductor_adapter",))
    execute("DELETE FROM vertex_jukyu_supply_node WHERE source_table = %s", ("vertex_open_smartphone_soc_design",))
    execute("DELETE FROM vertex_jukyu_supply_node WHERE source_table = %s", ("vertex_open_smartphone_ems_facility",))
    execute("DELETE FROM vertex_jukyu_supply_node WHERE source_table = %s", ("vertex_open_smartphone_soc_design:fab",))

    # ── Supply nodes: unique foundries (upstream, one node per fab_did) ────────
    # CTE avoids DISTINCT ON (RisingWave-safe).
    stats["fabNodes"] = execute(
        """
        WITH unique_fabs AS (
          SELECT fab_did, MIN(vertex_id) AS chip_vertex_id
          FROM vertex_open_smartphone_soc_design
          WHERE fab_did IS NOT NULL AND fab_did <> ''
            AND (status IS NULL OR status <> 'deleted')
          GROUP BY fab_did
        )
        INSERT INTO vertex_jukyu_supply_node
          (vertex_id, created_date, sensitivity_ord, owner_did, repo,
           domain, node_code, node_kind, display_name, country_code,
           operator_did, product_code, product_family, capacity_unit,
           status, source_table, source_vertex_id,
           collection, actor_did, org_did)
        SELECT
          'jukyu-node:semiconductor:fab:' || fab_did,
          CURRENT_DATE,
          1,
          'did:web:jukyu.etzhayyim.com',
          'did:web:jukyu.etzhayyim.com',
          'semiconductor',
          fab_did,
          'foundry',
          fab_did,
          'ZZ',
          fab_did,
          'wafer',
          'semiconductor_foundry',
          'wafers_month',
          'active',
          'vertex_open_smartphone_soc_design:fab',
          chip_vertex_id,
          'com.etzhayyim.apps.jukyu.supplyNode',
          'did:web:jukyu.etzhayyim.com',
          'did:web:etzhayyim.com'
        FROM unique_fabs
        """
    )

    # ── Supply nodes: SoC chip designs (intermediate nodes) ────────────────────
    stats["socNodes"] = execute(
        """
        INSERT INTO vertex_jukyu_supply_node
          (vertex_id, created_date, sensitivity_ord, owner_did, repo,
           domain, node_code, node_kind, display_name, country_code,
           operator_did, product_code, product_family, capacity_unit,
           status, source_table, source_vertex_id,
           collection, actor_did, org_did)
        SELECT
          'jukyu-node:semiconductor:soc:' || vertex_id,
          CURRENT_DATE,
          COALESCE(sensitivity_ord, 1),
          COALESCE(owner_did, 'did:web:jukyu.etzhayyim.com'),
          'did:web:jukyu.etzhayyim.com',
          'semiconductor',
          chip_id,
          'soc',
          chip_name,
          'ZZ',
          fab_did,
          COALESCE('nm' || CAST(process_node_nm AS VARCHAR), 'wafer'),
          'semiconductor_chip',
          'units',
          COALESCE(status, 'active'),
          'vertex_open_smartphone_soc_design',
          vertex_id,
          'com.etzhayyim.apps.jukyu.supplyNode',
          'did:web:jukyu.etzhayyim.com',
          'did:web:etzhayyim.com'
        FROM vertex_open_smartphone_soc_design
        WHERE status IS NULL OR status <> 'deleted'
        """
    )

    # ── Supply nodes: EMS assembly facilities (demand nodes) ──────────────────
    # operator_did synthesized as did:web:lei:{operator_lei} when present.
    # country_code uses location_iso3 directly — consistent within this domain.
    stats["emsNodes"] = execute(
        """
        INSERT INTO vertex_jukyu_supply_node
          (vertex_id, created_date, sensitivity_ord, owner_did, repo,
           domain, node_code, node_kind, display_name, country_code,
           operator_did, product_code, product_family, capacity_unit,
           demand_capacity, status, source_table, source_vertex_id,
           collection, actor_did, org_did)
        SELECT
          'jukyu-node:semiconductor:ems:' || vertex_id,
          CURRENT_DATE,
          COALESCE(sensitivity_ord, 1),
          COALESCE(owner_did, 'did:web:jukyu.etzhayyim.com'),
          'did:web:jukyu.etzhayyim.com',
          'semiconductor',
          facility_id,
          COALESCE(facility_type, 'ems'),
          operator_name,
          COALESCE(location_iso3, 'ZZ'),
          CASE
            WHEN operator_lei IS NOT NULL AND operator_lei <> ''
            THEN 'did:web:lei:' || operator_lei
            ELSE NULL
          END,
          'units',
          'semiconductor_assembly',
          'units_month',
          CAST(COALESCE(monthly_capacity_units, 0) AS DOUBLE PRECISION),
          COALESCE(status, 'active'),
          'vertex_open_smartphone_ems_facility',
          vertex_id,
          'com.etzhayyim.apps.jukyu.supplyNode',
          'did:web:jukyu.etzhayyim.com',
          'did:web:etzhayyim.com'
        FROM vertex_open_smartphone_ems_facility
        WHERE status IS NULL OR status <> 'deleted'
        """
    )

    # ── Supply dependencies: foundry → SoC (fab manufactures chip) ────────────
    stats["fabSocDeps"] = execute(
        """
        INSERT INTO edge_jukyu_supply_dependency
          (edge_id, src_vid, dst_vid, created_date, sensitivity_ord, owner_did,
           domain, relationship, product_code, product_family,
           dependency_weight, confidence, status)
        SELECT
          'jukyu-edge:semiconductor:fab-soc:' || d.vertex_id,
          fab_node.vertex_id,
          soc_node.vertex_id,
          CURRENT_DATE,
          1,
          'did:web:jukyu.etzhayyim.com',
          'semiconductor',
          'manufactures',
          COALESCE('nm' || CAST(d.process_node_nm AS VARCHAR), 'wafer'),
          'semiconductor_chip',
          CASE WHEN d.open_source_rtl THEN 0.8 ELSE 1.0 END,
          0.70,
          COALESCE(d.status, 'active')
        FROM vertex_open_smartphone_soc_design d
        INNER JOIN vertex_jukyu_supply_node fab_node
          ON fab_node.source_table = 'vertex_open_smartphone_soc_design:fab'
         AND fab_node.node_code = d.fab_did
         AND fab_node.domain = 'semiconductor'
        INNER JOIN vertex_jukyu_supply_node soc_node
          ON soc_node.source_table = 'vertex_open_smartphone_soc_design'
         AND soc_node.source_vertex_id = d.vertex_id
         AND soc_node.domain = 'semiconductor'
        WHERE d.fab_did IS NOT NULL AND d.fab_did <> ''
          AND (d.status IS NULL OR d.status <> 'deleted')
        """
    )

    # ── Supply dependencies: SoC → EMS (chip assembled into product) ──────────
    # vertex_open_smartphone_bom links soc_did → ems_facility_did.
    stats["socEmsDeps"] = execute(
        """
        INSERT INTO edge_jukyu_supply_dependency
          (edge_id, src_vid, dst_vid, created_date, sensitivity_ord, owner_did,
           domain, relationship, product_code, product_family,
           dependency_weight, confidence, status)
        SELECT
          'jukyu-edge:semiconductor:soc-ems:' || b.vertex_id,
          soc_node.vertex_id,
          ems_node.vertex_id,
          CURRENT_DATE,
          1,
          'did:web:jukyu.etzhayyim.com',
          'semiconductor',
          'assembled_by',
          'units',
          'semiconductor_assembly',
          0.85,
          0.65,
          COALESCE(b.status, 'active')
        FROM vertex_open_smartphone_bom b
        INNER JOIN vertex_jukyu_supply_node soc_node
          ON soc_node.source_table = 'vertex_open_smartphone_soc_design'
         AND soc_node.source_vertex_id = b.soc_did
         AND soc_node.domain = 'semiconductor'
        INNER JOIN vertex_jukyu_supply_node ems_node
          ON ems_node.source_table = 'vertex_open_smartphone_ems_facility'
         AND ems_node.source_vertex_id = b.ems_facility_did
         AND ems_node.domain = 'semiconductor'
        WHERE b.soc_did IS NOT NULL
          AND b.ems_facility_did IS NOT NULL
          AND (b.status IS NULL OR b.status <> 'deleted')
        """
    )

    # ── Company operate edges: fab and EMS operator DIDs → supply nodes ────────
    stats["companyOperateEdges"] = execute(
        """
        INSERT INTO edge_jukyu_company_operates_node
          (edge_id, src_vid, dst_vid, created_date, sensitivity_ord, owner_did,
           role, ownership_pct, confidence, status)
        SELECT
          'jukyu-operates:semiconductor:' || jsn.vertex_id,
          jsn.operator_did,
          jsn.vertex_id,
          CURRENT_DATE,
          1,
          'did:web:jukyu.etzhayyim.com',
          'operator',
          CAST(NULL AS DOUBLE PRECISION),
          CASE WHEN jsn.node_kind IN ('foundry', 'soc') THEN 0.70 ELSE 0.65 END,
          'active'
        FROM vertex_jukyu_supply_node jsn
        WHERE jsn.domain = 'semiconductor'
          AND jsn.operator_did IS NOT NULL
          AND jsn.operator_did <> ''
        """
    )

    # ── Balance observations: wafer demand aggregated by process node ──────────
    # Supply quantity is NULL (foundry capacity not in source schema).
    # Group by process_node_nm — the "commodity" dimension for semiconductor.
    stats["balanceObservations"] = execute(
        """
        INSERT INTO vertex_jukyu_balance_observation
          (vertex_id, created_date, sensitivity_ord, owner_did, repo,
           observation_id, domain, country_code, product_code, product_family,
           supply_quantity, demand_quantity, balance_quantity, quantity_unit,
           observed_at, source_kind, confidence, status, collection, actor_did, org_did)
        SELECT
          'jukyu-balance:semiconductor:nm'
            || COALESCE(CAST(o.process_node_nm AS VARCHAR), 'unknown') || ':latest',
          CURRENT_DATE,
          1,
          'did:web:jukyu.etzhayyim.com',
          'did:web:jukyu.etzhayyim.com',
          'semiconductor:nm'
            || COALESCE(CAST(o.process_node_nm AS VARCHAR), 'unknown') || ':latest',
          'semiconductor',
          'ZZ',
          COALESCE('nm' || CAST(o.process_node_nm AS VARCHAR), 'wafer'),
          'semiconductor_chip',
          CAST(NULL AS DOUBLE PRECISION),
          SUM(COALESCE(o.wafer_qty, 0))::DOUBLE PRECISION,
          -SUM(COALESCE(o.wafer_qty, 0))::DOUBLE PRECISION,
          'wafers',
          NOW()::VARCHAR,
          'semiconductor_adapter',
          0.55,
          'active',
          'com.etzhayyim.apps.jukyu.balanceObservation',
          'did:web:jukyu.etzhayyim.com',
          'did:web:etzhayyim.com'
        FROM vertex_open_smartphone_soc_fab_order o
        WHERE o.order_status IS NULL OR o.order_status NOT IN ('cancelled', 'rejected')
        GROUP BY o.process_node_nm
        """
    )

    # ── Company exposures: EMS operators (demand-side, chip shortage risk) ─────
    stats["companyExposures"] = execute(
        """
        INSERT INTO vertex_jukyu_company_exposure
          (vertex_id, created_date, sensitivity_ord, owner_did, repo,
           exposure_id, run_id, company_did, company_name, domain, country_code,
           product_code, product_family, supply_pressure, demand_pressure,
           downstream_pressure, structural_pressure, risk_score, confidence,
           evidence_json, recommended_action, status, collection, actor_did, org_did)
        SELECT
          'jukyu-exposure:semiconductor:' || e.vertex_id,
          CURRENT_DATE,
          1,
          'did:web:jukyu.etzhayyim.com',
          'did:web:jukyu.etzhayyim.com',
          'semiconductor:' || e.vertex_id,
          'jukyu.adapter.semiconductor.latest',
          CASE
            WHEN e.operator_lei IS NOT NULL AND e.operator_lei <> ''
            THEN 'did:web:lei:' || e.operator_lei
            ELSE 'did:web:ems:' || e.facility_id
          END,
          e.operator_name,
          'semiconductor',
          COALESCE(e.location_iso3, 'ZZ'),
          'units',
          'semiconductor_assembly',
          0.60,
          CASE
            WHEN COALESCE(e.monthly_capacity_units, 0) >= 100000 THEN 0.80
            WHEN COALESCE(e.monthly_capacity_units, 0) >= 10000  THEN 0.65
            ELSE 0.50
          END,
          0.55,
          CASE WHEN COALESCE(e.facility_type, '') = 'ems' THEN 0.65 ELSE 0.40 END,
          CASE
            WHEN COALESCE(e.monthly_capacity_units, 0) >= 100000 THEN 0.68
            WHEN COALESCE(e.monthly_capacity_units, 0) >= 10000  THEN 0.58
            ELSE 0.45
          END,
          0.55,
          '[{"source":"vertex_open_smartphone_ems_facility","reason":"EMS facility normalized into Jukyu SoS semiconductor domain"}]',
          'Diversify foundry sourcing, increase wafer safety stock, qualify alternate EMS facilities, and monitor export control alerts.',
          'active',
          'com.etzhayyim.apps.jukyu.companyExposure',
          'did:web:jukyu.etzhayyim.com',
          'did:web:etzhayyim.com'
        FROM vertex_open_smartphone_ems_facility e
        WHERE e.status IS NULL OR e.status <> 'deleted'
        """
    )

    for key, table in (
        ("jukyuSupplyNodesTotal", "vertex_jukyu_supply_node"),
        ("jukyuBalanceRowsTotal", "vertex_jukyu_balance_observation"),
        ("jukyuExposureRowsTotal", "vertex_jukyu_company_exposure"),
    ):
        row = fetch_one(f"SELECT COUNT(*) FROM {table} WHERE domain = %s", ("semiconductor",))
        stats[key] = int(row[0]) if row else 0

    return stats


def normalize_entity_vessel_transport(domain: str | None = None) -> dict[str, Any]:
    """Normalize legal entities, vessels, and transportation into Jukyu graph.

    This adapter does not invent entity records.  It links existing
    vertex_legal_entity / vertex_vessel_* / vertex_oil_cargo rows to Jukyu
    supply nodes and edges so the LangGraph can account for real operators,
    carriers, shipowners, vessels, and transport disruption.
    """

    target_domain = domain or "crude_oil"
    stats: dict[str, Any] = {"ok": True, "domain": target_domain, "adapter": "entity_vessel_transport"}

    execute("DELETE FROM edge_jukyu_transport_moves_product WHERE edge_id LIKE %s", (f"jukyu-transport-move:{target_domain}:%",))
    execute("DELETE FROM vertex_jukyu_transport_leg WHERE vertex_id LIKE %s", (f"jukyu-transport:{target_domain}:%",))
    execute("DELETE FROM edge_jukyu_entity_controls_node WHERE edge_id LIKE %s", (f"jukyu-controls:{target_domain}:%",))

    stats["entityControlEdges"] = execute(
        """
        INSERT INTO edge_jukyu_entity_controls_node
          (edge_id, src_vid, dst_vid, created_date, sensitivity_ord, owner_did,
           domain, role, ownership_pct, confidence, source_table, status)
        SELECT
          'jukyu-controls:' || n.domain || ':' || n.operator_did || ':' || n.vertex_id,
          n.operator_did,
          n.vertex_id,
          CAST(NOW() AS DATE),
          1,
          'did:web:jukyu.etzhayyim.com',
          n.domain,
          'operator',
          CAST(NULL AS DOUBLE PRECISION),
          CASE WHEN le.vertex_id IS NOT NULL THEN 0.86 ELSE 0.62 END,
          n.source_table,
          COALESCE(n.status, 'active')
        FROM vertex_jukyu_supply_node n
        LEFT JOIN vertex_legal_entity le ON le.vertex_id = n.operator_did
        WHERE n.domain = %s
          AND n.operator_did IS NOT NULL
          AND n.operator_did <> ''
          AND (n.status IS NULL OR n.status <> 'deleted')
        """,
        (target_domain,),
    )

    # Cargo movements become transport legs when load/discharge UN/LOCODEs
    # can be resolved to Jukyu nodes.  Vessel linkage is filled later when a
    # source cargo table carries IMO/MMSI; the MV already joins vessel rows.
    stats["transportLegsFromOilCargo"] = execute(
        """
        INSERT INTO vertex_jukyu_transport_leg
          (vertex_id, created_date, sensitivity_ord, owner_did, repo,
           leg_id, domain, supply_edge_id, cargo_vid, vessel_vid, vessel_imo,
           vessel_mmsi, origin_node_vid, destination_node_vid, origin_locode,
           destination_locode, carrier_did, shipowner_did, operator_did, charterer_did,
           product_code, product_family, quantity, quantity_unit, transport_mode,
           status, departure_at, eta_at, observed_at, eta_delay_hours,
           route_risk_score, confidence, evidence_json, source_table,
           source_vertex_id, collection, actor_did, org_did)
        SELECT
          'jukyu-transport:crude_oil:' || c.vertex_id,
          COALESCE(c.created_date, CAST(NOW() AS DATE)),
          COALESCE(c.sensitivity_ord, 1),
          COALESCE(c.owner_did, 'did:web:jukyu.etzhayyim.com'),
          COALESCE(c.repo, 'did:web:jukyu.etzhayyim.com'),
          COALESCE(c.cargo_id, c.vertex_id),
          'crude_oil',
          e.edge_id,
          c.vertex_id,
          CAST(NULL AS VARCHAR),
          CAST(NULL AS VARCHAR),
          CAST(NULL AS VARCHAR),
          src.vertex_id,
          dst.vertex_id,
          c.load_port,
          c.discharge_port,
          CAST(NULL AS VARCHAR),
          CAST(NULL AS VARCHAR),
          CAST(NULL AS VARCHAR),
          CAST(NULL AS VARCHAR),
          COALESCE(c.grade_code, c.commodity, 'CRUD'),
          'crude_oil',
          c.quantity::DOUBLE PRECISION,
          'bbl',
          'vessel',
          COALESCE(c.status, 'active'),
          c.laycan,
          CAST(NULL AS VARCHAR),
          NOW()::varchar,
          CAST(NULL AS DOUBLE PRECISION),
          COALESCE(e.route_risk_score, 0.20),
          0.56,
          '[{"source":"vertex_oil_cargo","reason":"cargo load/discharge ports linked to Jukyu supply nodes"}]',
          'vertex_oil_cargo',
          c.vertex_id,
          'com.etzhayyim.apps.jukyu.transportLeg',
          'did:web:jukyu.etzhayyim.com',
          'did:web:etzhayyim.com'
        FROM vertex_oil_cargo c
        INNER JOIN vertex_jukyu_supply_node src
          ON src.domain = 'crude_oil' AND src.locode = c.load_port
        INNER JOIN vertex_jukyu_supply_node dst
          ON dst.domain = 'crude_oil' AND dst.locode = c.discharge_port
        LEFT JOIN edge_jukyu_supply_dependency e
          ON e.domain = 'crude_oil' AND e.src_vid = src.vertex_id AND e.dst_vid = dst.vertex_id
        WHERE %s = 'crude_oil'
          AND (c.status IS NULL OR c.status <> 'deleted')
        """,
        (target_domain,),
    )

    stats["transportMoveEdges"] = execute(
        """
        INSERT INTO edge_jukyu_transport_moves_product
          (edge_id, src_vid, dst_vid, created_date, sensitivity_ord, owner_did,
           domain, relationship, product_code, product_family, quantity,
           quantity_unit, lead_time_days, dependency_weight, confidence, status)
        SELECT
          'jukyu-transport-move:' || domain || ':' || leg_id,
          origin_node_vid,
          destination_node_vid,
          COALESCE(created_date, CAST(NOW() AS DATE)),
          COALESCE(sensitivity_ord, 1),
          COALESCE(owner_did, 'did:web:jukyu.etzhayyim.com'),
          domain,
          'transports',
          product_code,
          product_family,
          quantity,
          quantity_unit,
          CAST(NULL AS DOUBLE PRECISION),
          CASE
            WHEN COALESCE(quantity, 0.0) <= 0.0 THEN 0.20
            WHEN quantity >= 1000000.0 THEN 1.0
            ELSE quantity / 1000000.0
          END,
          confidence,
          COALESCE(status, 'active')
        FROM vertex_jukyu_transport_leg
        WHERE domain = %s
          AND origin_node_vid IS NOT NULL
          AND destination_node_vid IS NOT NULL
          AND vertex_id LIKE %s
        """,
        (target_domain, f"jukyu-transport:{target_domain}:%"),
    )

    for key, table in (
        ("transportLegsTotal", "vertex_jukyu_transport_leg"),
        ("transportMoveEdgesTotal", "edge_jukyu_transport_moves_product"),
        ("entityControlsTotal", "edge_jukyu_entity_controls_node"),
    ):
        row = fetch_one(f"SELECT COUNT(*) FROM {table} WHERE domain = %s", (target_domain,))
        stats[key] = int(row[0]) if row else 0

    return stats
