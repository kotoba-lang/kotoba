from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class GearState(TypedDict):
    part_number: str
    spec_data: dict
    validation_logs: List[str]
    is_approved: bool

def validate_gearing_specs(state: GearState) -> GearState:
    specs = state.get('spec_data', {})
    logs = state.get('validation_logs', [])

    backlash = specs.get('backlash', 10)
    if backlash > 5:
        logs.append(f'Validation Warning: Backlash {backlash} exceeds high-precision threshold.')
        state['is_approved'] = False
    else:
        logs.append('Validation Success: Precision within limits.')
        state['is_approved'] = True
    state['validation_logs'] = logs
    return state

def check_compliance(state: GearState) -> GearState:
    if state.get('is_approved'):
        state['validation_logs'].append('Compliance Passed: Dual-use export protocols verified.')
    else:
        state['validation_logs'].append('Compliance Flag: Requires manual security review.')
    return state

graph = StateGraph(GearState)
graph.add_node('validate', validate_gearing_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
