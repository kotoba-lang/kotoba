from typing import TypedDict
from langgraph.graph import StateGraph, END

class FlushValveState(TypedDict):
    part_number: str
    is_sterile: bool
    pressure_test_passed: bool

def validate_valve(state: FlushValveState):
    if not state.get('is_sterile'):
        return {'status': 'rejected'}
    return {'status': 'approved' if state.get('pressure_test_passed') else 'pending_review'}

graph = StateGraph(FlushValveState)
graph.add_node('validate_valve', validate_valve)
graph.set_entry_point('validate_valve')
graph.add_edge('validate_valve', END)

graph = graph.compile()
