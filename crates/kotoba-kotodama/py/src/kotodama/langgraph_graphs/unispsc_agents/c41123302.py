from typing import TypedDict
from langgraph.graph import StateGraph, END

class LabSupplyState(TypedDict):
    item_name: str
    spec_compliance: bool
    validation_log: list

def validate_specs(state: LabSupplyState):
    log = state.get('validation_log', [])
    valid = True
    if 'slots' not in state.get('item_name', '').lower():
        log.append('Missing capacity spec')
        valid = False
    return {'spec_compliance': valid, 'validation_log': log}

graph = StateGraph(LabSupplyState)
graph.add_node('validator', validate_specs)
graph.set_entry_point('validator')
graph.add_edge('validator', END)
graph = graph.compile()
