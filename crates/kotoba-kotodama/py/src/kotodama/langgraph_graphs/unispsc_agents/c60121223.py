from typing import TypedDict
from langgraph.graph import StateGraph, END
class PaintSpecState(TypedDict):
    paint_type: str
    toxicity_certified: bool
    compliance_score: int
def validate_safety(state: PaintSpecState):
    state['toxicity_certified'] = True
    return state
def check_compliance(state: PaintSpecState):
    state['compliance_score'] = 100 if state['toxicity_certified'] else 0
    return state
graph = StateGraph(PaintSpecState)
graph.add_node('validate', validate_safety)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
