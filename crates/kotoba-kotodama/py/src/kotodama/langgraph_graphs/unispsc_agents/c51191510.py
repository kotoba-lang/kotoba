from typing import TypedDict
from langgraph.graph import StateGraph, END

class FurosemideState(TypedDict):
    batch_id: str
    compliance_check: bool
    temperature_logs: list
    release_status: str

def validate_compliance(state: FurosemideState):
    # Simulate GXP/Regulatory compliance validation logic
    state['compliance_check'] = True if state.get('batch_id') else False
    return {'compliance_check': state['compliance_check']}

def check_temp(state: FurosemideState):
    # Ensure storage conditions are met
    logs = state.get('temperature_logs', [])
    valid = all(15 <= t <= 25 for t in logs)
    return {'release_status': 'APPROVED' if valid else 'QUARANTINE'}

graph_builder = StateGraph(FurosemideState)
graph_builder.add_node('validate', validate_compliance)
graph_builder.add_node('temp_check', check_temp)
graph_builder.set_entry_point('validate')
graph_builder.add_edge('validate', 'temp_check')
graph_builder.add_edge('temp_check', END)
graph = graph_builder.compile()
