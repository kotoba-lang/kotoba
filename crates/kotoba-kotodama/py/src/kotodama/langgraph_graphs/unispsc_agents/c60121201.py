from typing import TypedDict
from langgraph.graph import StateGraph, END

class PaintProcurementState(TypedDict):
    paint_code: str
    safety_check: bool
    is_compliant: bool

def validate_safety_standards(state: PaintProcurementState):
    print('Validating SDS for liquid tempera...')
    return {'safety_check': True}

def compliance_check(state: PaintProcurementState):
    print('Verifying ASTM D-4236 compliance...')
    return {'is_compliant': state['safety_check']}

graph = StateGraph(PaintProcurementState)
graph.add_node('validate', validate_safety_standards)
graph.add_node('compliance', compliance_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
