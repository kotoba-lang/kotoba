from typing import TypedDict, List, Annotated
import operator
from langgraph.graph import StateGraph, END

class LivestockState(TypedDict):
    animal_ids: List[str]
    health_status: List[str]
    compliance_checks: Annotated[List[str], operator.add]

def validate_health_records(state: LivestockState):
    return {'compliance_checks': ['health_verified']}

def check_pedigree(state: LivestockState):
    return {'compliance_checks': ['pedigree_confirmed']}

def finalize_intake(state: LivestockState):
    return {'compliance_checks': ['intake_approved']}

graph = StateGraph(LivestockState)
graph.add_node('validate_health', validate_health_records)
graph.add_node('check_pedigree', check_pedigree)
graph.add_node('finalize', finalize_intake)
graph.set_entry_point('validate_health')
graph.add_edge('validate_health', 'check_pedigree')
graph.add_edge('check_pedigree', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
