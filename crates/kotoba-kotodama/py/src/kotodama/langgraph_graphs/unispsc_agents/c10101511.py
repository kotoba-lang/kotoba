from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CoalProcurementState(TypedDict):
    commodity_code: str
    quality_metrics: dict
    compliance_checks: List[str]
    approved: bool

def validate_coal_quality(state: CoalProcurementState):
    metrics = state.get('quality_metrics', {})
    if metrics.get('calorific_value', 0) > 5000 and metrics.get('sulfur_content', 1.0) < 0.5:
        return {'compliance_checks': ['quality_pass'], 'approved': True}
    return {'compliance_checks': ['quality_fail'], 'approved': False}

def security_and_risk_check(state: CoalProcurementState):
    # Sanctions and dangerous goods screening
    return {'compliance_checks': state['compliance_checks'] + ['security_pass']}

graph = StateGraph(CoalProcurementState)
graph.add_node('validate', validate_coal_quality)
graph.add_node('risk', security_and_risk_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'risk')
graph.add_edge('risk', END)

graph = graph.compile()
