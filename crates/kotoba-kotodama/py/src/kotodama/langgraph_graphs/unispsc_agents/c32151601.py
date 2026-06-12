from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PLCState(TypedDict):
    chassis_id: str
    validation_errors: List[str]
    is_compliant: bool

def validate_chassis(state: PLCState):
    # Simulate logic check for 32151601
    errors = []
    if not state.get('chassis_id'):
        errors.append('Missing Chassis ID')
    return {'validation_errors': errors, 'is_compliant': len(errors) == 0}

def route_by_compliance(state: PLCState):
    return 'compliant' if state['is_compliant'] else 'flag_for_review'

graph = StateGraph(PLCState)
graph.add_node('validate', validate_chassis)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance, {'compliant': END, 'flag_for_review': END})
graph = graph.compile()
