from typing import TypedDict
from langgraph.graph import StateGraph, END

class RivetState(TypedDict):
    material: str
    spec_compliance: bool
    validation_log: list

def validate_spec(state: RivetState):
    log = state.get('validation_log', [])
    valid = state.get('material') != 'unknown'
    log.append('Checked material compliance.')
    return {'spec_compliance': valid, 'validation_log': log}

graph = StateGraph(RivetState)
graph.add_node('validate', validate_spec)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
