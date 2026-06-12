from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ToolState(TypedDict):
    specs: dict
    is_compliant: bool
    validation_logs: List[str]

def validate_specs(state: ToolState):
    specs = state.get('specs', {})
    logs = []
    compliant = True
    if 'safety_cert' not in specs:
        logs.append('Missing safety certification')
        compliant = False
    return {'is_compliant': compliant, 'validation_logs': logs}

def process_procurement(state: ToolState):
    return {'validation_logs': state['validation_logs'] + ['Procurement approved']}

graph = StateGraph(ToolState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)

graph = graph.compile()
