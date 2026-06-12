from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity_id: str
    validation_steps: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_commodity(state: ProcurementState) -> ProcurementState:
    # Logic for commodity-specific validation
    return {**state, 'is_compliant': True, 'validation_steps': ['basic_validation']}

def audit_risk(state: ProcurementState) -> ProcurementState:
    # Logic for risk assessment
    return {**state, 'validation_steps': ['risk_assessment']}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_commodity)
graph.add_node('audit', audit_risk)
graph.add_edge('validate', 'audit')
graph.add_edge('audit', END)
graph.set_entry_point('validate')
graph = graph.compile()
