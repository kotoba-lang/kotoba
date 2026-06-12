from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_id: str
    spec_data: dict
    validation_passed: bool
    log: List[str]

def validate_specs(state: ProcurementState):
    log = state.get('log', [])
    specs = state.get('spec_data', {})
    passed = all(key in specs for key in ['origin_country', 'moisture_content_percent'])
    log.append(f'Validation result: {passed}')
    return {'validation_passed': passed, 'log': log}

def compliance_check(state: ProcurementState):
    log = state.get('log', [])
    log.append('Running compliance audit...')
    return {'log': log}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', compliance_check)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
