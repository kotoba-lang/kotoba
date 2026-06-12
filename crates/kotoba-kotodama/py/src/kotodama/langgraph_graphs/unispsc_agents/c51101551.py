from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class CommodityState(TypedDict):
    purity_level: float
    test_results: Annotated[List[str], operator.add]
    status: str

def validate_purity(state: CommodityState) -> CommodityState:
    if state.get('purity_level', 0) >= 99.9:
        state['test_results'].append('Purity check passed')
        state['status'] = 'VALIDATED'
    else:
        state['status'] = 'REJECTED'
    return state

def check_storage(state: CommodityState) -> CommodityState:
    if state.get('status') == 'VALIDATED':
        state['test_results'].append('Storage requirements verified')
    return state

graph = StateGraph(CommodityState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_storage', check_storage)
graph.add_edge('validate_purity', 'check_storage')
graph.add_edge('check_storage', END)
graph.set_entry_point('validate_purity')
graph = graph.compile()
