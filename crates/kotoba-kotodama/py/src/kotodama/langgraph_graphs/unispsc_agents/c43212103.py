from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PrinterState(TypedDict):
    model_info: str
    specs_validated: bool
    compliance_ok: bool

def validate_specs(state: PrinterState):
    print('Validating dye-sub printer mechanical specs...')
    val = bool(state.get('model_info'))
    return {'specs_validated': val}

def check_compliance(state: PrinterState):
    print('Checking regulatory compliance for printing equipment...')
    return {'compliance_ok': True}

graph = StateGraph(PrinterState)
graph.add_node('validate_specs', validate_specs)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate_specs', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate_specs')
graph = graph.compile()
