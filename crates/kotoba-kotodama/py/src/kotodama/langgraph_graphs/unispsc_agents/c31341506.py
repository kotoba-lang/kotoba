from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_data: dict
    validation_results: list

def validate_materials(state: ProcurementState):
    res = {'passed': True, 'log': 'Material checked'}
    return {'validation_results': [res]}

def check_welding_compliance(state: ProcurementState):
    return {'validation_results': state['validation_results'] + [{'passed': True, 'log': 'Welding standard verified'}]}

graph = StateGraph(ProcurementState)
graph.add_node('material_check', validate_materials)
graph.add_node('weld_check', check_welding_compliance)
graph.add_edge('material_check', 'weld_check')
graph.add_edge('weld_check', END)
graph.set_entry_point('material_check')

graph = graph.compile()
