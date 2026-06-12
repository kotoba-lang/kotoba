from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class LubricantState(TypedDict):
    lubricant_id: str
    spec_data: dict
    validation_log: List[str]
    is_compliant: bool

def validate_spec(state: LubricantState) -> LubricantState:
    log = state.get('validation_log', [])
    spec = state.get('spec_data', {})
    # Logic: Validate Flash point and Viscosity requirements
    compliant = spec.get('flash_point', 0) > 200 and spec.get('viscosity', 0) > 10
    log.append(f'Validation result: {compliant}')
    return {'validation_log': log, 'is_compliant': compliant}

def route_by_compliance(state: LubricantState):
    return 'compliant' if state['is_compliant'] else 'flag_for_review'

graph = StateGraph(LubricantState)
graph.add_node('validate', validate_spec)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance, {'compliant': END, 'flag_for_review': END})
graph = graph.compile()
