from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    material_grade: str
    welding_certified: bool
    passed_qa: bool

def validate_materials(state: AssemblyState):
    return {'passed_qa': state.get('material_grade') in ['304', '316L']}

def structural_check(state: AssemblyState):
    return {'passed_qa': state.get('welding_certified') == True}

graph = StateGraph(AssemblyState)
graph.add_node('material_check', validate_materials)
graph.add_node('weld_check', structural_check)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'weld_check')
graph.add_edge('weld_check', END)

graph = graph.compile()
