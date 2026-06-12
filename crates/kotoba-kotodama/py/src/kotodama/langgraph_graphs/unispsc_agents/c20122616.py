from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class RobotState(TypedDict):
    robot_id: str
    specs: dict
    validation_log: Annotated[List[str], operator.add]
    is_approved: bool

def validate_specs(state: RobotState):
    specs = state.get('specs', {})
    log = []
    if specs.get('payload_capacity_kg', 0) > 0:
        log.append(f'Payload capacity validated: {specs.get('payload_capacity_kg')}kg')
    else:
        log.append('Payload capacity invalid')
    return {'validation_log': log}

def safety_review(state: RobotState):
    log = ['Safety review initiated']
    return {'validation_log': log, 'is_approved': True}

workflow = StateGraph(RobotState)
workflow.add_node('validate', validate_specs)
workflow.add_node('safety', safety_review)
workflow.add_edge('validate', 'safety')
workflow.add_edge('safety', END)
workflow.set_entry_point('validate')
graph = workflow.compile()
