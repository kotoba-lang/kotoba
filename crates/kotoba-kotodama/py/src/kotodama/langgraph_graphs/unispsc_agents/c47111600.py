from typing import TypedDict
from langgraph.graph import StateGraph, END

class IroningSpecState(TypedDict):
    power_supply: str
    thermal_safety_check: bool
    compliance_verified: bool

def validate_power(state: IroningSpecState):
    state['power_supply'] = 'Verified' if state.get('power_supply') else 'Pending'
    return state

def run_safety_audit(state: IroningSpecState):
    state['thermal_safety_check'] = True
    return state

graph = StateGraph(IroningSpecState)
graph.add_node('validate_power', validate_power)
graph.add_node('run_safety_audit', run_safety_audit)
graph.set_entry_point('validate_power')
graph.add_edge('validate_power', 'run_safety_audit')
graph.add_edge('run_safety_audit', END)
graph = graph.compile()
