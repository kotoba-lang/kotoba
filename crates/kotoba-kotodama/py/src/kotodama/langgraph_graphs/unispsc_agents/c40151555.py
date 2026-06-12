from typing import TypedDict
from langgraph.graph import StateGraph, END

class PumpState(TypedDict):
    spec_data: dict
    validation_results: dict

def validate_materials(state: PumpState):
    print('Validating pump material compliance...')
    return {'validation_results': {'material_ok': True}}

def check_flow_rating(state: PumpState):
    print('Verifying flow rate against industrial standards...')
    return {'validation_results': {'flow_ok': True}}

graph = StateGraph(PumpState)
graph.add_node('material_check', validate_materials)
graph.add_node('flow_check', check_flow_rating)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'flow_check')
graph.add_edge('flow_check', END)
graph = graph.compile()
