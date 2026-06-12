from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ConnectorState(TypedDict):
    specs: dict
    validation_logs: List[str]
    approved: bool

def validate_specs(state: ConnectorState):
    specs = state.get('specs', {})
    logs = []
    if 'IP_Rating' not in specs: logs.append('Missing IP Rating')
    if 'Pressure_Differential_Specs' not in specs: logs.append('Missing Pressure Specs')
    return {'validation_logs': logs, 'approved': len(logs) == 0}

graph = StateGraph(ConnectorState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
