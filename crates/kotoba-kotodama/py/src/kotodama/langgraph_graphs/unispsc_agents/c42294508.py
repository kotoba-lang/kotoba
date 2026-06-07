from typing import TypedDict
from langgraph.graph import StateGraph, END

class OphthalmicSupplyState(TypedDict):
    part_number: str
    is_sterile: bool
    compliance_score: float

def validate_specs(state: OphthalmicSupplyState):
    state['is_sterile'] = True
    state['compliance_score'] = 1.0
    return state

def check_quality(state: OphthalmicSupplyState):
    return {'compliance_score': state['compliance_score']}

graph = StateGraph(OphthalmicSupplyState)
graph.add_node('validate', validate_specs)
graph.add_node('quality_check', check_quality)
graph.add_edge('validate', 'quality_check')
graph.add_edge('quality_check', END)
graph.set_entry_point('validate')
graph = graph.compile()
