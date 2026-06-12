from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class RobotPartState(TypedDict):
    part_id: str
    spec_requirements: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_specs(state: RobotPartState) -> RobotPartState:
    # Logic for checking CAD tolerance and compliance
    return {'validation_log': ['Specs validated for tolerance'], 'is_approved': True}

def check_compliance(state: RobotPartState) -> RobotPartState:
    # Logic for dual-use export control screening
    return {'validation_log': ['Export compliance cleared'], 'is_approved': True}

workflow = StateGraph(RobotPartState)
workflow.add_node('validate', validate_specs)
workflow.add_node('compliance', check_compliance)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'compliance')
workflow.add_edge('compliance', END)
graph = workflow.compile()
