from typing import TypedDict
from langgraph.graph import StateGraph, END

class BatteryState(TypedDict):
    voltage: float
    capacity_mah: float
    shelf_life_status: str
    compliance_ok: bool

def validate_battery_specs(state: BatteryState):
    state['compliance_ok'] = state.get('voltage', 0) > 0 and state.get('capacity_mah', 0) > 0
    return {'compliance_ok': state['compliance_ok']}

def check_shelf_life(state: BatteryState):
    return {'shelf_life_status': 'Validated' if state['compliance_ok'] else 'Expired'}

graph = StateGraph(BatteryState)
graph.add_node('validate', validate_battery_specs)
graph.add_node('shelf_life', check_shelf_life)
graph.add_edge('validate', 'shelf_life')
graph.add_edge('shelf_life', END)
graph.set_entry_point('validate')
graph = graph.compile()
