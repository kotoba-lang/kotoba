from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class MailSupplyState(TypedDict):
    items: List[str]
    validation_results: dict
    approved: bool

def validate_materials(state: MailSupplyState):
    # Simulate material compliance check
    return {'validation_results': {'material_check': 'passed'}}

def check_dimensions(state: MailSupplyState):
    # Simulate size compliance check
    return {'validation_results': {'dimension_check': 'passed'}}

graph = StateGraph(MailSupplyState)
graph.add_node('material_validation', validate_materials)
graph.add_node('dimension_validation', check_dimensions)
graph.set_entry_point('material_validation')
graph.add_edge('material_validation', 'dimension_validation')
graph.add_edge('dimension_validation', END)

graph = graph.compile()
