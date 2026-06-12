from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ProcurementState(TypedDict):
    items: List[str]
    compliance_passed: bool
    inspection_result: str

def validate_food_grade(state: ProcurementState):
    # Simulate food safety compliance check
    return {'compliance_passed': True}

def perform_inspection(state: ProcurementState):
    return {'inspection_result': 'passed'}

graph = StateGraph(ProcurementState)
graph.add_node('validate_food_grade', validate_food_grade)
graph.add_node('perform_inspection', perform_inspection)
graph.set_entry_point('validate_food_grade')
graph.add_edge('validate_food_grade', 'perform_inspection')
graph.add_edge('perform_inspection', END)

graph = graph.compile()
