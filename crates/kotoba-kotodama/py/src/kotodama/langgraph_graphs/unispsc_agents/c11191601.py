from typing import TypedDict, Annotated, List, Any
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    catalyst_id: str
    purity_level: float
    validation_logs: List[str]
    approved: bool

def validate_catalyst_purity(state: CatalystState):
    purity = state.get('purity_level', 0.0)
    if purity >= 99.5:
        return {'validation_logs': ['Purity check passed: >= 99.5%'], 'approved': True}
    return {'validation_logs': ['Purity check failed'], 'approved': False}

def prepare_logistics(state: CatalystState):
    if state['approved']:
        return {'validation_logs': state['validation_logs'] + ['Logistics routing initiated']}
    return {'validation_logs': state['validation_logs'] + ['Logistics pending rejection review']}

graph = StateGraph(CatalystState)
graph.add_node('validate', validate_catalyst_purity)
graph.add_node('logistics', prepare_logistics)
graph.add_edge('validate', 'logistics')
graph.add_edge('logistics', END)
graph.set_entry_point('validate')
graph = graph.compile()
