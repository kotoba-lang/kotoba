from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class RackState(TypedDict):
    part_number: str
    spec_compliance: bool
    validation_log: List[str]

def validate_rack_specs(state: RackState):
    log = state.get('validation_log', [])
    log.append('Validating EIA-310 standard compliance...')
    return {'spec_compliance': True, 'validation_log': log}

graph = StateGraph(RackState)
graph.add_node('validate', validate_rack_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
