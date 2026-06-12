from typing import TypedDict
from langgraph.graph import StateGraph, END

class ASGState(TypedDict):
    part_number: str
    compliance_docs: list
    pressure_test_passed: bool

def validate_compliance(state: ASGState):
    return {'compliance_docs': ['ISO13485', 'CE_Mark']}

def conduct_pressure_test(state: ASGState):
    return {'pressure_test_passed': True}

workflow = StateGraph(ASGState)
workflow.add_node('compliance', validate_compliance)
workflow.add_node('pressure_test', conduct_pressure_test)
workflow.set_entry_point('compliance')
workflow.add_edge('compliance', 'pressure_test')
workflow.add_edge('pressure_test', END)
graph = workflow.compile()
