from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PrinterState(TypedDict):
    model_number: str
    spec_compliance: bool
    validation_logs: List[str]

def validate_specs(state: PrinterState):
    # Simulate CAD/Spec validation for professional printing equipment
    is_compliant = True if state.get('model_number') else False
    return {'spec_compliance': is_compliant, 'validation_logs': ['Model verified', 'Specs checked']}

def finalize_procurement(state: PrinterState):
    return {'validation_logs': state['validation_logs'] + ['Procurement ready']}

workflow = StateGraph(PrinterState)
workflow.add_node('validate', validate_specs)
workflow.add_node('finalize', finalize_procurement)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'finalize')
workflow.add_edge('finalize', END)

graph = workflow.compile()
