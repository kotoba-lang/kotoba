from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class RobotEndEffectorState(TypedDict):
    task_id: str
    specs: dict
    validation_log: list
    is_approved: bool

def validate_specs(state: RobotEndEffectorState):
    specs = state.get('specs', {})
    log = []
    if specs.get('load_capacity_kg', 0) <= 0:
        log.append('Invalid load capacity')
    return {'validation_log': log, 'is_approved': len(log) == 0}

def route_by_validation(state: RobotEndEffectorState):
    return 'approve' if state.get('is_approved') else 'flag'

def approve_procurement(state: RobotEndEffectorState):
    return {'validation_log': ['Procurement approved for high-precision components']}

def flag_for_review(state: RobotEndEffectorState):
    return {'validation_log': ['Review required: potential dual-use item']}

graph = StateGraph(RobotEndEffectorState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approve_procurement)
graph.add_node('flag', flag_for_review)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation)
graph.add_edge('approve', END)
graph.add_edge('flag', END)
graph = graph.compile()
