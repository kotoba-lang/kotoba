from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class OfficePaperState(TypedDict):
    item_id: str
    quantity: int
    spec_compliance: bool
    validation_log: List[str]

def validate_paper_spec(state: OfficePaperState) -> OfficePaperState:
    log = state.get('validation_log', [])
    log.append('Validating material density and acid-free status.')
    return {'spec_compliance': True, 'validation_log': log}

def update_inventory(state: OfficePaperState) -> OfficePaperState:
    log = state.get('validation_log', [])
    log.append('Updating central warehouse inventory count.')
    return {'validation_log': log}

graph = StateGraph(OfficePaperState)
graph.add_node('validate', validate_paper_spec)
graph.add_node('inventory', update_inventory)
graph.add_edge('validate', 'inventory')
graph.add_edge('inventory', END)
graph.set_entry_point('validate')
graph = graph.compile()
