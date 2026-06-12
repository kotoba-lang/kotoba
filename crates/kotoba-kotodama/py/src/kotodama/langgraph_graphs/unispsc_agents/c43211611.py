from langgraph.graph import StateGraph, END
from typing import TypedDict
class PDAState(TypedDict):
    device_list: list
    validation_results: dict
    approved: bool
def validate_specs(state: PDAState):
    return {'validation_results': {'status': 'compliant', 'battery_check': 'passed'}}
def check_compatibility(state: PDAState):
    return {'approved': True}
graph = StateGraph(PDAState)
graph.add_node('validate', validate_specs)
graph.add_node('compatibility', check_compatibility)
graph.add_edge('validate', 'compatibility')
graph.add_edge('compatibility', END)
graph.set_entry_point('validate')
graph = graph.compile()
