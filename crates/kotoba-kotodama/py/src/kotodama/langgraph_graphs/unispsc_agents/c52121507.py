from typing import TypedDict
from langgraph.graph import StateGraph, END
class FeatherbedState(TypedDict):
    material_certified: bool
    flammability_tested: bool
    quality_score: float
def validate_materials(state: FeatherbedState):
    state['material_certified'] = True
    return state
def check_compliance(state: FeatherbedState):
    state['flammability_tested'] = True
    return state
graph = StateGraph(FeatherbedState)
graph.add_node('validate', validate_materials)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
