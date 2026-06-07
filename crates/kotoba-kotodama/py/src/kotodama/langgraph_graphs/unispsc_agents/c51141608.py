from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PharmaState(TypedDict):
    api_name: str
    purity_check: bool
    compliance_docs: List[str]
    status: str

def validate_api(state: PharmaState):
    is_pure = state.get('purity_check', False)
    docs = state.get('compliance_docs', [])
    if is_pure and 'GMP_CERT' in docs:
        return {'status': 'CLEARED_FOR_PROCUREMENT'}
    return {'status': 'QA_HOLD'}

graph = StateGraph(PharmaState)
graph.add_node('validate', validate_api)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
