from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class DentalCassetteState(TypedDict):
    specifications: dict
    validation_results: List[str]
    approved: bool

def validate_materials(state: DentalCassetteState):
    material = state.get('specifications', {}).get('material', '')
    status = 'Pass' if material in ['Stainless Steel', 'Medical Grade Plastic'] else 'Fail'
    return {'validation_results': [f'Material validation: {status}']}

def check_autoclave_specs(state: DentalCassetteState):
    temp_rating = state.get('specifications', {}).get('max_temp', 0)
    status = 'Pass' if temp_rating >= 134 else 'Fail'
    return {'validation_results': state['validation_results'] + [f'Autoclave spec: {status}']}

graph = StateGraph(DentalCassetteState)
graph.add_node('material_check', validate_materials)
graph.add_node('autoclave_check', check_autoclave_specs)
graph.add_edge('material_check', 'autoclave_check')
graph.add_edge('autoclave_check', END)
graph.set_entry_point('material_check')

graph = graph.compile()
