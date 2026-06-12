from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DeviceState(TypedDict):
    device_id: str
    regulatory_status: bool
    test_results: List[float]
    is_approved: bool

def validate_compliance(state: DeviceState):
    # Regulatory logic for assistive devices
    status = state.get('regulatory_status', False)
    return {'is_approved': status}

def audit_performance(state: DeviceState):
    # Threshold check for sound amplification
    results = state.get('test_results', [])
    passed = all(r > 0.8 for r in results)
    return {'is_approved': passed and state.get('is_approved', False)}

graph = StateGraph(DeviceState)
graph.add_node('validate', validate_compliance)
graph.add_node('audit', audit_performance)
graph.add_edge('validate', 'audit')
graph.add_edge('audit', END)
graph.set_entry_point('validate')
graph = graph.compile()
