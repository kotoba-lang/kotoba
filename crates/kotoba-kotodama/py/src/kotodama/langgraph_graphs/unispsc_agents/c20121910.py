from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class ActuatorState(TypedDict):
    spec_data: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_specs(state: ActuatorState):
    specs = state.get('spec_data', {})
    log = []
    if 'torque_rating_nm' not in specs:
        log.append('Missing torque rating')
    return {'validation_log': log}

def compliance_check(state: ActuatorState):
    is_compliant = len(state.get('validation_log', [])) == 0
    return {'is_compliant': is_compliant}

graph = StateGraph(ActuatorState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', compliance_check)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
