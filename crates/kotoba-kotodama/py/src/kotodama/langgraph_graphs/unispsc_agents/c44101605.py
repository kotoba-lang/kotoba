from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class JoggerProcurementState(TypedDict):
    model_number: str
    specifications: dict
    is_compliant: bool
    validation_report: List[str]

def validate_specs(state: JoggerProcurementState):
    specs = state.get('specifications', {})
    report = []
    compliant = True
    if 'max_sheet_size' not in specs:
        report.append('Missing sheet size specification.')
        compliant = False
    return {'is_compliant': compliant, 'validation_report': report}

workflow = StateGraph(JoggerProcurementState)
workflow.add_node('validate', validate_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
