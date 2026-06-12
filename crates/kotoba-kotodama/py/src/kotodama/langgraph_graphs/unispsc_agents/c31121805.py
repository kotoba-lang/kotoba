from typing import TypedDict
from langgraph.graph import StateGraph, END

class MoldState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_mold_specs(state: MoldState):
    specs = state.get('spec_data', {})
    required = ['tolerance', 'material_grade']
    passed = all(k in specs for k in required) and specs.get('tolerance') < 0.05
    return {'validation_passed': passed}

graph = StateGraph(MoldState)
graph.add_node('validate', validate_mold_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
