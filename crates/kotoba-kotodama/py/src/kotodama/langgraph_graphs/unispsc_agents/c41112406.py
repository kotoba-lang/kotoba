from typing import TypedDict
from langgraph.graph import StateGraph, END

class VacuumGaugeState(TypedDict):
    pressure_range: str
    calibration_cert: bool
    is_compliant: bool

def validate_specs(state: VacuumGaugeState):
    # Business logic for vacuum gauge regulatory compliance check
    if not state.get('calibration_cert'):
        return {'is_compliant': False}
    return {'is_compliant': True}

workflow = StateGraph(VacuumGaugeState)
workflow.add_node('validate', validate_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
