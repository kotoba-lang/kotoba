from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
import operator

class SeedProcurementState(TypedDict):
    seed_id: str
    batch_id: str
    purity_score: float
    germination_status: str
    log: Annotated[List[str], operator.add]

def validate_purity(state: SeedProcurementState):
    purity = state.get('purity_score', 0.0)
    if purity >= 0.95:
        return {'germination_status': 'proceed', 'log': ['Purity check passed']}
    return {'germination_status': 'reject', 'log': ['Purity check failed']}

def conduct_germination_test(state: SeedProcurementState):
    return {'germination_status': 'verified', 'log': ['Germination test completed']}

graph = StateGraph(SeedProcurementState)
graph.add_node('validate', validate_purity)
graph.add_node('germinate', conduct_germination_test)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', lambda x: x['germination_status'], {'proceed': 'germinate', 'reject': END})
graph.add_edge('germinate', END)
graph = graph.compile()
