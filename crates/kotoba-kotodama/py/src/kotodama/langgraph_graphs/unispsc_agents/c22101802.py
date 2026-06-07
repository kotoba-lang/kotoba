from typing import TypedDict
from langgraph.graph import StateGraph, END

class AnchorBoltState(TypedDict):
    bolt_specs: dict
    compliance_score: float
    final_approval: bool

def validate_specs(state: AnchorBoltState):
    specs = state.get('bolt_specs', {})
    score = 1.0 if 'tensile_strength' in specs and 'grade' in specs else 0.5
    return {'compliance_score': score, 'final_approval': score == 1.0}

graph = StateGraph(AnchorBoltState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
