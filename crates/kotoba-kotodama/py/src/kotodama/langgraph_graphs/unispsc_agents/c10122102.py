from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class FungiProcurementState(TypedDict):
    commodity_id: str
    batch_id: str
    quality_score: float
    inspection_steps: Annotated[List[str], operator.add]
    is_approved: bool

def validate_freshness(state: FungiProcurementState) -> dict:
    # Logic to verify harvest date and moisture levels
    return {'inspection_steps': ['freshness_check_passed'], 'quality_score': 0.95}

def check_compliance(state: FungiProcurementState) -> dict:
    # Logic to check hygiene certification
    return {'inspection_steps': ['compliance_check_passed'], 'is_approved': True}

graph = StateGraph(FungiProcurementState)
graph.add_node('freshness', validate_freshness)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('freshness')
graph.add_edge('freshness', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
