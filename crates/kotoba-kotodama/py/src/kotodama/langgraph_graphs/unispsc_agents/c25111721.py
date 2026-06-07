from typing import TypedDict
from langgraph.graph import StateGraph, END

class CraftState(TypedDict):
    hull_integrity: bool
    engine_status: str
    compliance_passed: bool

def check_hull(state: CraftState): return {'hull_integrity': True}
def verify_compliance(state: CraftState): return {'compliance_passed': True}

graph = StateGraph(CraftState)
graph.add_node('check_hull', check_hull)
graph.add_node('verify_compliance', verify_compliance)
graph.set_entry_point('check_hull')
graph.add_edge('check_hull', 'verify_compliance')
graph.add_edge('verify_compliance', END)
graph = graph.compile()
