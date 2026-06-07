from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CellCultureState(TypedDict):
    reagent_id: str
    purity_check: bool
    sterility_verified: bool
    workflow_status: str

def validate_purity(state: CellCultureState) -> CellCultureState:
    # Logic to verify chemical purity specs
    state['purity_check'] = True
    return state

def verify_sterility(state: CellCultureState) -> CellCultureState:
    # Logic to verify sterile condition/certification
    state['sterility_verified'] = True
    return state

graph = StateGraph(CellCultureState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('verify_sterility', verify_sterility)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'verify_sterility')
graph.add_edge('verify_sterility', END)
graph = graph.compile()
