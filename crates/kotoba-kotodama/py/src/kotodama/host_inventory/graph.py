"""LangGraph workflow for host_inventory.

Nodes
-----
1. collect_device  — sysctl/ioreg
2. collect_disks   — df / diskutil
3. collect_power   — battery + thermal (fan-out to async because slow)
4. collect_displays
5. collect_apps    — /Applications scan
6. collect_processes — ps -A
7. collect_launchitems — LaunchAgents/Daemons

Returns a single state dict that `persist.persist_host_inventory` consumes.
"""

from __future__ import annotations

import asyncio
from typing import Any, TypedDict

from langgraph.graph import StateGraph, END

from .device import collect_device, collect_disks, collect_battery, collect_displays
from .apps import collect_installed_apps, collect_processes, collect_launchitems


class InventoryState(TypedDict, total=False):
    device: dict[str, Any]
    disks: list[dict[str, Any]]
    battery: dict[str, Any] | None
    displays: list[dict[str, Any]]
    installed_apps: list[dict[str, Any]]
    processes: list[dict[str, Any]]
    launchitems: list[dict[str, Any]]
    error: str


async def _async(fn, *args, **kwargs):
    return await asyncio.get_event_loop().run_in_executor(None, lambda: fn(*args, **kwargs))


async def device_node(_: InventoryState) -> dict:
    return {"device": await _async(collect_device)}


async def disks_node(_: InventoryState) -> dict:
    return {"disks": await _async(collect_disks)}


async def power_node(_: InventoryState) -> dict:
    return {"battery": await _async(collect_battery)}


async def displays_node(_: InventoryState) -> dict:
    return {"displays": await _async(collect_displays)}


async def apps_node(_: InventoryState) -> dict:
    return {"installed_apps": await _async(collect_installed_apps)}


async def processes_node(_: InventoryState) -> dict:
    return {"processes": await _async(collect_processes)}


async def launchitems_node(_: InventoryState) -> dict:
    return {"launchitems": await _async(collect_launchitems)}


def build_host_inventory_graph():
    g = StateGraph(InventoryState)
    g.add_node("device", device_node)
    g.add_node("disks", disks_node)
    g.add_node("power", power_node)
    g.add_node("displays", displays_node)
    g.add_node("apps", apps_node)
    g.add_node("processes", processes_node)
    g.add_node("launchitems", launchitems_node)
    g.set_entry_point("device")
    g.add_edge("device", "disks")
    g.add_edge("disks", "power")
    g.add_edge("power", "displays")
    g.add_edge("displays", "apps")
    g.add_edge("apps", "processes")
    g.add_edge("processes", "launchitems")
    g.add_edge("launchitems", END)
    return g.compile()


async def run_host_inventory() -> dict:
    graph = build_host_inventory_graph()
    return await graph.ainvoke({})
