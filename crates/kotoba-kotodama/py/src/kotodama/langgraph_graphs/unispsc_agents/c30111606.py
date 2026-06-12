from typing import TypedDict
from langgraph.graph import StateGraph, END
class GroutState(TypedDict):
    spec_data: dict
    validation_result: bool
def validate_grout_specs(state: GroutState):
    specs = state.get('spec_data', {})
    required = ['compressive_strength_mpa', 'setting_time_minutes']
    valid = all(k in specs for k in required) and specs['compressive_strength_mpa'] > 40
    return {'validation_result': valid}
def finalize_procurement(state: GroutState):
    return {'validation_result': True}
graph = StateGraph(GroutState)
graph.add_node('validate', validate_grout_specs)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
