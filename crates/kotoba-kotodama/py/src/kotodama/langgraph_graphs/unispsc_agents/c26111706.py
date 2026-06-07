from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BatteryState(TypedDict):
    battery_type: str
    compliance_docs: List[str]
    safety_check_passed: bool

def validate_battery_safety(state: BatteryState):
    # logic for checking UN38.3 certification
    state['safety_check_passed'] = 'UN38.3' in state.get('compliance_docs', [])
    return state

def route_by_safety(state: BatteryState):
    return 'pass' if state['safety_check_passed'] else 'fail'

graph = StateGraph(BatteryState)
graph.add_node('safety_check', validate_battery_safety)
graph.add_edge('safety_check', END)
graph.set_entry_point('safety_check')
graph = graph.compile()
