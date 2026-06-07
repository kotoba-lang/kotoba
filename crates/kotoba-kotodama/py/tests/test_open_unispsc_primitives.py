from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_open_unispsc_commodity_runs_hierarchy_business_logic():
    from kotodama.primitives.open_unispsc import task_open_unispsc_commodity

    result = await task_open_unispsc_commodity(
        code="43211501",
        name="Computer servers",
        quantity=2,
        unitPrice=1000,
        currency="USD",
        dryRun=True,
    )

    assert result["ok"] is True
    levels = [r["level"] for r in result["results"]]
    assert levels == ["segment", "family", "class", "commodity"]
    commodity = result["results"][-1]
    assert commodity["code"] == "43211501"
    assert commodity["hierarchy"] == {
        "segment": "43",
        "family": "4321",
        "class": "432115",
        "commodity": "43211501",
    }
    assert commodity["parentLevel"] == "class"
    assert commodity["parentCode"] == "432115"
    assert commodity["businessLogic"]["approvalTier"] == "standard"
    assert commodity["businessLogic"]["totalAmount"] == 2000
    assert commodity["mcpTool"] == "com.etzhayyim.apps.openUnispsc.commodity"


@pytest.mark.asyncio
async def test_open_unispsc_segment_is_own_business_boundary():
    from kotodama.primitives.open_unispsc import task_open_unispsc_segment

    result = await task_open_unispsc_segment(code="46", dryRun=True)

    assert result["ok"] is True
    assert [r["level"] for r in result["results"]] == ["segment"]
    segment = result["results"][0]
    assert segment["did"] == "did:web:unispsc.etzhayyim.com:seg46"
    assert segment["businessLogic"]["strategy"] == "controlled-safety-and-defense"
    assert "arms-or-security-review" in segment["businessLogic"]["riskTags"]


@pytest.mark.asyncio
async def test_open_unispsc_family_rejects_wrong_grain():
    from kotodama.primitives.open_unispsc import task_open_unispsc_family

    result = await task_open_unispsc_family(code="43", dryRun=True)

    assert result["ok"] is False
    assert "4 digits" in result["error"]


@pytest.mark.asyncio
async def test_mcp_dispatch_registers_open_unispsc_hierarchy_tools():
    from kotodama.mcp_dispatch import build_actor_handlers, build_default_handlers, handle_envelope

    handlers = build_default_handlers()
    for name in [
        "com.etzhayyim.apps.openUnispsc.segment",
        "com.etzhayyim.apps.openUnispsc.family",
        "com.etzhayyim.apps.openUnispsc.class",
        "com.etzhayyim.apps.openUnispsc.commodity",
        "com.etzhayyim.apps.openUnispsc.designItem",
        "com.etzhayyim.apps.openUnispsc.itemGetSpec",
        "com.etzhayyim.apps.openUnispsc.itemScreenSupplier",
        "com.etzhayyim.apps.openUnispsc.itemPlanProcurement",
        "com.etzhayyim.apps.openUnispsc.itemFlagCompliance",
        "com.etzhayyim.apps.openUnispsc.syncCatalogItem",
        "com.etzhayyim.apps.openUnispsc.planCatalogPurchase",
        "com.etzhayyim.apps.openUnispsc.syncAllCommodityDids",
        "com.etzhayyim.apps.openUnispsc.importSegmentCatalog",
        "com.etzhayyim.apps.openUnispsc.supplier",
        "com.etzhayyim.apps.openUnispsc.procurement",
        "com.etzhayyim.apps.openUnispsc.flagArmsCommodity",
        "com.etzhayyim.apps.openUnispsc.flagDualUseCommodity",
        "com.etzhayyim.apps.openUnispsc.applyGraphWritePlan",
        "com.etzhayyim.apps.openUnispsc.runItemWorkflow",
        "com.etzhayyim.apps.openUnispsc.coverageSnapshot",
    ]:
        assert name in handlers

    status, body = await handle_envelope(
        {
            "method": "tools/call",
            "params": {
                "name": "com.etzhayyim.apps.openUnispsc.class",
                "arguments": {"code": "432115", "dryRun": True},
            },
        },
        handlers,
    )
    assert status == 200
    assert body["result"]["ok"] is True
    assert [r["level"] for r in body["result"]["results"]] == ["segment", "family", "class"]

    scoped_handlers = build_actor_handlers({"openUnispsc"})
    assert set(scoped_handlers) == {
        name for name in handlers
        if name.startswith("com.etzhayyim.apps.openUnispsc.")
    }
    assert all(name.startswith("com.etzhayyim.apps.openUnispsc.") for name in scoped_handlers)


@pytest.mark.asyncio
async def test_open_unispsc_design_item_uses_bpmn_and_langchain_contract():
    from kotodama.primitives.open_unispsc import task_open_unispsc_design_item

    result = await task_open_unispsc_design_item(
        commodityCode="25172504",
        commodityName="Vehicle Batteries",
    )

    assert result["ok"] is True
    assert result["mcpTool"] == "com.etzhayyim.apps.openUnispsc.designItem"
    assert result["langgraph_design"]["graphId"] == "open_unispsc_item_25172504"
    assert "procurement_plan" in result["langgraph_design"]["nodes"]
    assert "supplier_screen" in result["langgraph_design"]["nodes"]
    assert result["langchain_prompt"]["framework"] == "langchain"
    bpmn_ids = {r["processId"] for r in result["bpmn_refs"]}
    assert "open_unispsc_procurement" in bpmn_ids
    assert "open_unispsc_supplier" in bpmn_ids


@pytest.mark.asyncio
async def test_open_unispsc_design_item_adds_arms_bpmn_for_segment_46():
    from kotodama.primitives.open_unispsc import task_open_unispsc_design_item

    result = await task_open_unispsc_design_item(
        commodityCode="46101501",
        commodityName="Firearms",
    )

    bpmn_ids = {r["processId"] for r in result["bpmn_refs"]}
    assert "open_unispsc_flag_arms_commodity" in bpmn_ids
    assert "arms_control_gate" in result["langgraph_design"]["nodes"]


@pytest.mark.asyncio
async def test_open_unispsc_item_get_spec_is_executable_contract():
    from kotodama.primitives.open_unispsc import task_open_unispsc_item_get_spec

    result = await task_open_unispsc_item_get_spec(
        commodityCode="25172504",
        commodityName="Vehicle Batteries",
    )

    assert result["ok"] is True
    assert result["operation"] == "getSpec"
    assert result["mcpTool"] == "com.etzhayyim.apps.openUnispsc.itemGetSpec"
    assert result["specTemplate"]["quality"] == ["standards", "certifications", "inspectionCriteria"]
    assert result["langgraphDesign"]["graphId"] == "open_unispsc_item_25172504"
    assert result["langchainPrompt"]["framework"] == "langchain"


@pytest.mark.asyncio
async def test_open_unispsc_item_screen_supplier_follows_supplier_bpmn_rules():
    from kotodama.primitives.open_unispsc import task_open_unispsc_item_screen_supplier

    result = await task_open_unispsc_item_screen_supplier(
        commodityCode="25172504",
        supplierDid="did:web:supplier.example",
        country="JPN",
        kycCleared=True,
        qualityScore=0.8,
    )

    assert result["ok"] is True
    assert result["riskTier"] == "approved"
    assert result["requireManualKyc"] is False
    assert result["bpmnProcessId"] == "open_unispsc_supplier"


@pytest.mark.asyncio
async def test_open_unispsc_item_plan_procurement_follows_procurement_bpmn_rules():
    from kotodama.primitives.open_unispsc import task_open_unispsc_item_plan_procurement

    result = await task_open_unispsc_item_plan_procurement(
        commodityCode="25172504",
        buyerOrgId="did:web:buyer.example",
        quantity=2,
        unitPrice=600000,
        currency="USD",
    )

    assert result["ok"] is True
    assert result["totalAmount"] == 1200000
    assert result["approvalTier"] == "enterprise"
    assert result["requireCab"] is True
    assert result["auditAction"] == "openUnispsc.procurement.cabRequest"


@pytest.mark.asyncio
async def test_open_unispsc_item_flag_compliance_uses_arms_and_dualuse_bpmn():
    from kotodama.primitives.open_unispsc import task_open_unispsc_item_flag_compliance

    result = await task_open_unispsc_item_flag_compliance(
        commodityCode="46101501",
        commodityName="Firearms",
    )

    assert result["ok"] is True
    assert result["arms"] is True
    assert result["dualUse"] is True
    assert result["severity"] == "high"
    assert "open_unispsc_flag_arms_commodity" in result["bpmnProcessIds"]


@pytest.mark.asyncio
async def test_open_unispsc_sync_catalog_item_maps_to_okaimono_catalog_contract():
    from kotodama.primitives.open_unispsc import task_open_unispsc_sync_catalog_item

    result = await task_open_unispsc_sync_catalog_item(
        commodityCode="43211501",
        commodityName="Computer servers",
        sourceRepo="did:web:unispsc.etzhayyim.com:seg43",
        rkey="43211501",
    )

    assert result["ok"] is True
    assert result["mcpTool"] == "com.etzhayyim.apps.openUnispsc.syncCatalogItem"
    assert result["sourceCollection"] == "com.etzhayyim.apps.unispsc.commodity"
    assert result["catalogCollection"] == "com.etzhayyim.apps.okaimono.catalogItem"
    assert result["catalogRkey"] == "unispsc-43211501"
    assert result["catalogItem"] == {
        "product_id": "unispsc-43211501",
        "sku": "UNSPSC-43211501",
        "title": "Computer servers",
        "category": "unispsc:43:4321:432115",
        "unispsc_code": "43211501",
        "unispsc_segment": "43",
        "unispsc_family": "4321",
        "unispsc_class": "432115",
        "commodity_did": "did:web:unispsc.etzhayyim.com:seg43:commodity:c43211501",
        "active": True,
    }
    assert result["atprotoWritePlan"]["mode"] == "deterministic-upsert"
    assert result["atprotoWritePlan"]["collection"] == "com.etzhayyim.apps.okaimono.catalogItem"
    assert result["classificationEdge"]["role"] == "CLASSIFIED_BY"


@pytest.mark.asyncio
async def test_open_unispsc_plan_catalog_purchase_invokes_segment_item_spec():
    from kotodama.primitives.open_unispsc import task_open_unispsc_plan_catalog_purchase

    result = await task_open_unispsc_plan_catalog_purchase(
        productId="unispsc-43211501",
        orderId="order-001",
        customerDid="did:web:customer.example",
        buyerOrgId="did:web:buyer.example",
        quantity=1,
        unitPrice=2400,
        currency="USD",
    )

    assert result["ok"] is True
    assert result["mcpTool"] == "com.etzhayyim.apps.openUnispsc.planCatalogPurchase"
    assert result["commodityCode"] == "43211501"
    assert result["orderLine"] == {
        "orderId": "order-001",
        "productId": "unispsc-43211501",
        "quantity": 1.0,
        "unitPrice": 2400.0,
        "currency": "USD",
    }
    assert result["checkoutSaga"]["sagaId"] == "chk8uty2"
    assert result["procurementInvocation"] == {
        "step": "procurement-find-offers",
        "targetActorDid": "did:web:unispsc.etzhayyim.com:seg43",
        "mcpTool": "com.etzhayyim.apps.openUnispsc.itemGetSpec",
        "arguments": {"commodityCode": "43211501"},
    }
    assert result["fulfillmentPlan"]["step"] == "fulfillment-create-shipment"
    assert result["purchaseFlow"] == [
        "catalog-search",
        "order-create",
        "checkout-saga",
        "procurement-find-offers",
        "item-get-spec",
        "fulfillment-create-shipment",
    ]


@pytest.mark.asyncio
async def test_open_unispsc_sync_all_commodity_dids_plans_segment_fanout():
    from kotodama.primitives.open_unispsc import task_open_unispsc_sync_all_commodity_dids

    result = await task_open_unispsc_sync_all_commodity_dids(
        segmentCodes=["44", "46"],
        batchSize=250,
        dryRun=True,
    )

    assert result["ok"] is True
    assert result["mcpTool"] == "com.etzhayyim.apps.openUnispsc.syncAllCommodityDids"
    assert result["dryRun"] is True
    assert result["segmentCount"] == 2
    assert result["batchSize"] == 250
    plan = result["orchestrationPlan"]
    assert plan["mode"] == "cross-actor-fanout"
    assert plan["operation"] == "sync-all-commodity-dids"
    assert plan["commandsPerSegment"] == 3
    first = plan["segments"][0]
    assert first["segment"] == "44"
    assert first["targetActorDid"] == "did:web:unispsc.etzhayyim.com:seg44"
    assert [cmd["command"] for cmd in first["commands"]] == [
        "register-commodities-bulk",
        "register-commodity-profiles",
        "post-commodity-registration-feed",
    ]


@pytest.mark.asyncio
async def test_open_unispsc_import_segment_catalog_plans_bulk_okaimono_import():
    from kotodama.primitives.open_unispsc import task_open_unispsc_import_segment_catalog

    result = await task_open_unispsc_import_segment_catalog(
        segmentCode="46",
        pageSize=750,
        dryRun=True,
    )

    assert result["ok"] is True
    assert result["mcpTool"] == "com.etzhayyim.apps.openUnispsc.importSegmentCatalog"
    assert result["segment"] == "46"
    assert result["importCommand"] == "import-unispsc-segment"
    assert result["sourceQuery"] == {
        "graph": "unispsc_commodities",
        "where": {"segment": "46"},
        "orderBy": ["code"],
        "pageSize": 750,
    }
    assert result["importPlan"]["mode"] == "bulk-query-to-catalog-upsert"
    assert result["importPlan"]["transformTool"] == "com.etzhayyim.apps.openUnispsc.syncCatalogItem"
    assert result["importPlan"]["targetCollection"] == "com.etzhayyim.apps.okaimono.catalogItem"


@pytest.mark.asyncio
async def test_open_unispsc_supplier_matches_bpmn_lexicon_tool():
    from kotodama.primitives.open_unispsc import task_open_unispsc_supplier

    result = await task_open_unispsc_supplier(
        supplierDid="did:web:supplier.example",
        commodityCode="25172504",
        country="IRN",
        kycCleared=True,
        qualityScore=0.95,
        registeredAt="2026-05-14T00:00:00Z",
    )

    assert result["ok"] is True
    assert result["riskTier"] == "blocked"
    assert result["bpmnProcessId"] == "open_unispsc_supplier"
    assert result["vertexId"].startswith("at://did:web:unispsc.etzhayyim.com/com.etzhayyim.apps.openUnispsc.supplier/")
    assert result["instanceKey"] > 0
    assert result["mcpTool"] == "com.etzhayyim.apps.openUnispsc.supplier"
    assert result["status"] == "blocked"
    write_plan = result["graphWritePlan"]
    assert write_plan["mode"] == "deterministic-upsert"
    assert write_plan["operation"] == "upsertOpenUnispscSupplier"
    assert write_plan["rows"][0]["table"] == "vertex_open_unispsc_supplier"
    assert write_plan["rows"][0]["record"]["risk_tier"] == "blocked"
    assert write_plan["rows"][0]["record"]["registered_at"] == "2026-05-14T00:00:00Z"


@pytest.mark.asyncio
async def test_open_unispsc_procurement_matches_bpmn_lexicon_tool():
    from kotodama.primitives.open_unispsc import task_open_unispsc_procurement

    result = await task_open_unispsc_procurement(
        buyerOrgId="did:web:buyer.example",
        commodityCode="25172504",
        quantity=10,
        unitPrice=6000,
        currency="USD",
        submittedAt="2026-05-14T00:00:00Z",
    )

    assert result["ok"] is True
    assert result["totalAmount"] == 60000
    assert result["approvalTier"] == "department"
    assert result["requireCab"] is False
    assert result["bpmnProcessId"] == "open_unispsc_procurement"
    assert result["mcpTool"] == "com.etzhayyim.apps.openUnispsc.procurement"
    assert result["status"] == "submitted"
    write_plan = result["graphWritePlan"]
    assert write_plan["mode"] == "deterministic-upsert"
    assert write_plan["operation"] == "upsertOpenUnispscProcurement"
    assert [row["table"] for row in write_plan["rows"]] == [
        "vertex_open_unispsc_procurement",
        "edge_open_unispsc_procurement_commodity",
    ]
    procurement_row = write_plan["rows"][0]["record"]
    assert procurement_row["commodity_code"] == "25172504"
    assert procurement_row["approval_tier"] == "department"
    assert procurement_row["submitted_at"] == "2026-05-14T00:00:00Z"
    edge_row = write_plan["rows"][1]["record"]
    assert edge_row["src_vid"] == result["vertexId"]
    assert edge_row["dst_vid"] == "did:web:unispsc.etzhayyim.com:seg25:commodity:c25172504"


@pytest.mark.asyncio
async def test_open_unispsc_direct_flag_tools_match_bpmn_lexicons():
    from kotodama.primitives.open_unispsc import (
        task_open_unispsc_flag_arms_commodity,
        task_open_unispsc_flag_dual_use_commodity,
    )

    arms = await task_open_unispsc_flag_arms_commodity(
        vertexId="v1",
        commodityVid="did:web:unispsc.etzhayyim.com:seg46:commodity:c46101501",
        unspscCode="46101501",
        subFamily="Firearms",
        detectedAt="2026-05-14T00:00:00Z",
    )
    dual = await task_open_unispsc_flag_dual_use_commodity(
        vertexId="v2",
        commodityVid="did:web:unispsc.etzhayyim.com:seg25:commodity:c25172504",
        unspscCode="25172504",
        dualUseCategory="battery-export-control",
        detectedAt="2026-05-14T00:00:00Z",
    )

    assert arms["ok"] is True
    assert arms["bpmnProcessId"] == "open_unispsc_flag_arms_commodity"
    assert arms["mcpTool"] == "com.etzhayyim.apps.openUnispsc.flagArmsCommodity"
    assert arms["graphWritePlan"]["operation"] == "upsertOpenUnispscArmsDefenceEvent"
    assert arms["graphWritePlan"]["rows"][0]["table"] == "vertex_open_defence_event"
    assert arms["graphWritePlan"]["rows"][0]["record"]["action_class"] == "commodity.arms"
    assert arms["graphWritePlan"]["rows"][0]["record"]["commodity_code"] == "46101501"
    assert dual["ok"] is True
    assert dual["bpmnProcessId"] == "open_unispsc_flag_dual_use_commodity"
    assert dual["mcpTool"] == "com.etzhayyim.apps.openUnispsc.flagDualUseCommodity"
    assert dual["graphWritePlan"]["operation"] == "upsertOpenUnispscDualUseDefenceEvent"
    assert dual["graphWritePlan"]["rows"][0]["record"]["action_class"] == "commodity.dualUse"


@pytest.mark.asyncio
async def test_open_unispsc_apply_graph_write_plan_validates_and_previews_sql():
    from kotodama.primitives.open_unispsc import (
        task_open_unispsc_apply_graph_write_plan,
        task_open_unispsc_procurement,
    )

    procurement = await task_open_unispsc_procurement(
        buyerOrgId="did:web:buyer.example",
        commodityCode="25172504",
        quantity=10,
        unitPrice=6000,
        currency="USD",
        submittedAt="2026-05-14T00:00:00Z",
    )
    result = await task_open_unispsc_apply_graph_write_plan(
        graphWritePlan=procurement["graphWritePlan"],
        dryRun=True,
    )

    assert result["ok"] is True
    assert result["dryRun"] is True
    assert result["validatedRows"] == 2
    assert result["appliedRows"] == 0
    assert result["mcpTool"] == "com.etzhayyim.apps.openUnispsc.applyGraphWritePlan"
    assert result["sqlStatements"][0]["sql"].startswith("INSERT INTO vertex_open_unispsc_procurement")
    assert "ON CONFLICT (vertex_id)" in result["sqlStatements"][0]["sql"]
    assert result["sqlStatements"][1]["sql"].startswith("INSERT INTO edge_open_unispsc_procurement_commodity")
    assert "ON CONFLICT (edge_id)" in result["sqlStatements"][1]["sql"]


@pytest.mark.asyncio
async def test_open_unispsc_apply_graph_write_plan_rejects_unknown_table():
    from kotodama.primitives.open_unispsc import task_open_unispsc_apply_graph_write_plan

    result = await task_open_unispsc_apply_graph_write_plan(
        graphWritePlan={
            "mode": "deterministic-upsert",
            "operation": "bad",
            "rows": [{"table": "vertex_unrelated", "key": "vertex_id", "record": {"vertex_id": "v1"}}],
        },
        dryRun=True,
    )

    assert result["ok"] is False
    assert result["validatedRows"] == 0
    assert "not an allowed openUnispsc graph table" in result["errors"][0]


@pytest.mark.asyncio
async def test_open_unispsc_apply_graph_write_plan_accepts_defence_event_flags():
    from kotodama.primitives.open_unispsc import (
        task_open_unispsc_apply_graph_write_plan,
        task_open_unispsc_flag_arms_commodity,
    )

    arms = await task_open_unispsc_flag_arms_commodity(
        vertexId="v1",
        commodityVid="did:web:unispsc.etzhayyim.com:seg46:commodity:c46101501",
        unspscCode="46101501",
        subFamily="Firearms",
        detectedAt="2026-05-14T00:00:00Z",
    )
    result = await task_open_unispsc_apply_graph_write_plan(
        graphWritePlan=arms["graphWritePlan"],
        dryRun=True,
    )

    assert result["ok"] is True
    assert result["validatedRows"] == 1
    assert result["sqlStatements"][0]["sql"].startswith("INSERT INTO vertex_open_defence_event")
    assert "ON CONFLICT (vertex_id)" in result["sqlStatements"][0]["sql"]
    assert "commodity.arms" in result["sqlStatements"][0]["parameters"]


@pytest.mark.asyncio
async def test_open_unispsc_run_item_workflow_merges_all_graph_plans():
    from kotodama.primitives.open_unispsc import (
        task_open_unispsc_apply_graph_write_plan,
        task_open_unispsc_run_item_workflow,
    )

    workflow = await task_open_unispsc_run_item_workflow(
        commodityCode="46101501",
        commodityName="Firearms",
        supplierDid="did:web:supplier.example",
        legalName="Supplier Example",
        country="JPN",
        kycCleared=True,
        qualityScore=0.8,
        buyerOrgId="did:web:buyer.example",
        quantity=2,
        unitPrice=600000,
        currency="USD",
        eventAt="2026-05-14T00:00:00Z",
    )

    assert workflow["ok"] is True
    assert workflow["mcpTool"] == "com.etzhayyim.apps.openUnispsc.runItemWorkflow"
    assert workflow["workflowStatus"] == "manual-review"
    assert workflow["summary"]["supplierRiskTier"] == "approved"
    assert workflow["summary"]["requireCab"] is True
    assert workflow["summary"]["arms"] is True
    assert workflow["summary"]["dualUse"] is True
    assert workflow["summary"]["defenceEventCount"] == 2
    assert workflow["graphWriteValidation"]["ok"] is True
    assert [row["table"] for row in workflow["graphWritePlan"]["rows"]] == [
        "vertex_open_unispsc_supplier",
        "vertex_open_unispsc_procurement",
        "edge_open_unispsc_procurement_commodity",
        "vertex_open_defence_event",
        "vertex_open_defence_event",
    ]

    preview = await task_open_unispsc_apply_graph_write_plan(
        graphWritePlan=workflow["graphWritePlan"],
        dryRun=True,
    )
    assert preview["ok"] is True
    assert preview["validatedRows"] == 5


@pytest.mark.asyncio
async def test_open_unispsc_run_item_workflow_blocks_sanctioned_supplier():
    from kotodama.primitives.open_unispsc import task_open_unispsc_run_item_workflow

    workflow = await task_open_unispsc_run_item_workflow(
        commodityCode="25172504",
        commodityName="Vehicle Batteries",
        supplierDid="did:web:supplier.example",
        country="IRN",
        kycCleared=True,
        qualityScore=0.9,
        buyerOrgId="did:web:buyer.example",
        quantity=1,
        unitPrice=1000,
        currency="USD",
        eventAt="2026-05-14T00:00:00Z",
    )

    assert workflow["ok"] is True
    assert workflow["workflowStatus"] == "blocked"
    assert workflow["summary"]["supplierRiskTier"] == "blocked"


@pytest.mark.asyncio
async def test_open_unispsc_coverage_snapshot_reports_complete_contract_surface():
    from kotodama.primitives.open_unispsc import task_open_unispsc_coverage_snapshot

    result = await task_open_unispsc_coverage_snapshot()

    assert result["ok"] is True
    assert result["toolCount"] == 20
    assert result["missing"] == []
    assert result["alembicPresent"] is True
    assert result["alembicReferencesUpSql"] is True
    assert result["alembicReferencesDownSql"] is True
    nsids = {tool["nsid"] for tool in result["tools"]}
    assert "com.etzhayyim.apps.openUnispsc.runItemWorkflow" in nsids
    assert "com.etzhayyim.apps.openUnispsc.coverageSnapshot" in nsids
    workflow = next(tool for tool in result["tools"] if tool["nsid"] == "com.etzhayyim.apps.openUnispsc.runItemWorkflow")
    assert workflow["handlerFunctionPresent"] is True
    assert workflow["handlerRegistered"] is True
    assert workflow["lexiconPresent"] is True
    assert workflow["lexiconValid"] is True
    assert workflow["seedRegistered"] is True
    assert workflow["downRegistered"] is True
    assert set(workflow["bpmnPresent"].values()) == {True}
    assert set(workflow["graphTargetsAllowed"].values()) == {True}
    assert all(tool["handlerFunctionPresent"] for tool in result["tools"])
    assert all(tool["handlerRegistered"] for tool in result["tools"])
    assert all(tool["lexiconValid"] for tool in result["tools"])
    assert all(tool["seedRegistered"] for tool in result["tools"])
    assert all(tool["downRegistered"] for tool in result["tools"])
