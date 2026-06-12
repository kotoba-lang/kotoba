from langgraph.graph import StateGraph, END
from typing import TypedDict
class JewelryState(TypedDict):
    material_compliance: bool
    safety_check: bool
    final_approval: str
def validate_materials(state: JewelryState):
    return {'material_compliance': True}
def verify_safety(state: JewelryState):
    return {'safety_check': True}
def finalize_procurement(state: JewelryState):
    return {'final_approval': 'APPROVED'}
graph = StateGraph(JewelryState)
graph.add_node('validate', validate_materials)
graph.add_node('safety', verify_safety)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
