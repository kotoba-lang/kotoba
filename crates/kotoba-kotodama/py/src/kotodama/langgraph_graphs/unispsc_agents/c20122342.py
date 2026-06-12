from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class RobotState(TypedDict):
    task_id: str
    specs: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_specs(state: RobotState):
    specs = state.get('specs', {})
    log = []
    if specs.get('payload_capacity_kg', 0) <= 0:
        log.append('Invalid payload capacity')
    return {'validation_log': log}

def decision_node(state: RobotState):
    if len(state['validation_log']) == 0:
        return 'approve'
    return 'reject'

def approve(state: RobotState):
    return {'is_approved': True}

def reject(state: RobotState):
    return {'is_approved': False}

graph = StateGraph(RobotState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approve)
graph.add_node('reject', reject)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', decision_node, {'approve': 'approve', 'reject': 'reject'})
graph.add_edge('approve', END)
graph.add_edge('reject', END)
graph = graph.compile()
