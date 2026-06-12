from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PotassiumProcurementState(TypedDict):
    spec_data: dict
    validation_errors: List[str]
    is_compliant: bool

def validate_supplement_specs(state: PotassiumProcurementState):
    errors = []
    required = ['Certificate_of_Analysis', 'Compliance_Certification']
    for field in required:
        if field not in state.get('spec_data', {}):
            errors.append(f'Missing mandatory field: {field}')
    return {'validation_errors': errors, 'is_compliant': len(errors) == 0}

workflow = StateGraph(PotassiumProcurementState)
workflow.add_node('validate', validate_supplement_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
