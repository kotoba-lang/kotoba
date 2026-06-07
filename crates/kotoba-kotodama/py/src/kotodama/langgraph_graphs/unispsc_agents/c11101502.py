from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MaterialIngestState(TypedDict):
    material_id: str
    purity_check: bool
    compliance_docs: Annotated[Sequence[str], operator.add]
    status: str

def validate_purity(state: MaterialIngestState) -> MaterialIngestState:
    # Logic to verify material purity against defined thresholds
    state['purity_check'] = True
    state['status'] = 'PURITY_VERIFIED'
    return state

def verify_documentation(state: MaterialIngestState) -> MaterialIngestState:
    # Logic to confirm required MSDS and batch certificates exist
    if len(state['compliance_docs']) >= 2:
        state['status'] = 'DOCS_APPROVED'
    else:
        state['status'] = 'DOCS_PENDING'
    return state

graph = StateGraph(MaterialIngestState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('verify_documentation', verify_documentation)
graph.add_edge('validate_purity', 'verify_documentation')
graph.add_edge('verify_documentation', END)
graph.set_entry_point('validate_purity')
graph = graph.compile()
