from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ActuatorState(TypedDict):
    spec_requirements: dict
    validation_logs: Annotated[List[str], add_messages]
    is_compliant: bool

def validate_spec(state: ActuatorState):
    specs = state.get('spec_requirements', {})
    torque = specs.get('torque_rating_nm', 0)
    if torque > 0:
        return {'validation_logs': ['Torque validated'], 'is_compliant': True}
    return {'validation_logs': ['Invalid torque specs'], 'is_compliant': False}

def route_compliance(state: ActuatorState):
    return 'compliant' if state['is_compliant'] else 'non_compliant'

graph = StateGraph(ActuatorState)
graph.add_node('validate', validate_spec)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_compliance, {'compliant': END, 'non_compliant': END})

graph = graph.compile()
