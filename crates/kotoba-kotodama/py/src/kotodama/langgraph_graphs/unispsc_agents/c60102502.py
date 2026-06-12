from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class OperationsModelState(TypedDict):
    model_type: str
    specifications: dict
    is_compliant: bool
    validation_log: List[str]

def validate_specs(state: OperationsModelState):
    specs = state.get('specifications', {})
    log = []
    compliant = True
    if 'material' not in specs:
        log.append('Missing material specification')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': log}

def route_by_compliance(state: OperationsModelState):
    return 'process' if state['is_compliant'] else 'flag_error'

graph = StateGraph(OperationsModelState)
graph.add_node('validate', validate_specs)
graph.add_node('process', lambda s: s)
graph.add_node('flag_error', lambda s: s)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance)
graph.add_edge('process', END)
graph.add_edge('flag_error', END)
graph = graph.compile()
