from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    part_id: str
    spec_data: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_specs(state: RobotState):
    specs = state.get('spec_data', {})
    log = []
    if specs.get('precision_tolerance_mm', 1.0) > 0.05:
        log.append('Tolerance exceeds precision limit.')
    return {'validation_log': log}

def approval_check(state: RobotState):
    return {'is_approved': len(state['validation_log']) == 0}

graph = StateGraph(RobotState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
