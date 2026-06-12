from typing import TypedDict
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    specs: dict
    validated: bool
    compliance_report: str

def validate_specs(state: RobotState):
    specs = state.get('specs', {})
    is_valid = all(k in specs for k in ['payload', 'reach'])
    print(f'Validating specs: {is_valid}')
    return {'validated': is_valid}

def safety_check(state: RobotState):
    print('Running industrial safety compliance check...')
    return {'compliance_report': 'Safety standards verified'}

graph = StateGraph(RobotState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', safety_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
