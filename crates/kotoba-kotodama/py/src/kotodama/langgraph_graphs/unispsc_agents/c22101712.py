from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotPartState(TypedDict):
    part_id: str
    specs: dict
    validated: bool
    compliance_report: str

def validate_specs(state: RobotPartState):
    # Business logic for technical validation of components
    specs = state.get('specs', {})
    is_valid = specs.get('load_capacity', 0) > 0 and 'iso_compliance' in specs
    return {'validated': is_valid}

def export_review(state: RobotPartState):
    # Logic for dual-use export control routing
    return {'compliance_report': 'CHECKED_FOR_DUAL_USE'}

graph = StateGraph(RobotPartState)
graph.add_node('validate', validate_specs)
graph.add_node('export_review', export_review)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_review')
graph.add_edge('export_review', END)
graph = graph.compile()
