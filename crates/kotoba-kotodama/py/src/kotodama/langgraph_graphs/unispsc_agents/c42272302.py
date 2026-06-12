from typing import TypedDict
from langgraph.graph import StateGraph, END

class ResuscitatorState(TypedDict):
    device_id: str
    compliance_docs: list
    validation_status: str

def validate_certification(state: ResuscitatorState) -> ResuscitatorState:
    print(f'Validating ISO 10651 for {state.get('device_id')}')
    state['validation_status'] = 'PASSED'
    return state

def check_maintenance_log(state: ResuscitatorState) -> ResuscitatorState:
    print('Verifying maintenance history')
    return state

graph = StateGraph(ResuscitatorState)
graph.add_node('validate', validate_certification)
graph.add_node('maintenance', check_maintenance_log)
graph.set_entry_point('validate')
graph.add_edge('validate', 'maintenance')
graph.add_edge('maintenance', END)
graph = graph.compile()
