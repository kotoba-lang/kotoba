from langgraph.graph import StateGraph, END
from typing import TypedDict
class DrugProcurementState(TypedDict):
    drug_name: str
    regulatory_approval: bool
    purity_validated: bool
    status: str
def validate_regulatory(state: DrugProcurementState):
    state['regulatory_approval'] = True
    return {'regulatory_approval': True}
def validate_quality(state: DrugProcurementState):
    state['purity_validated'] = True
    return {'purity_validated': True}
graph = StateGraph(DrugProcurementState)
graph.add_node('regulatory', validate_regulatory)
graph.add_node('quality', validate_quality)
graph.set_entry_point('regulatory')
graph.add_edge('regulatory', 'quality')
graph.add_edge('quality', END)
graph = graph.compile()
