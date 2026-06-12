from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolingState(TypedDict):
    part_number: str
    spec_compliance: bool
    export_control_check: bool

def validate_specs(state: ToolingState) -> ToolingState:
    print(f'Validating steel insert specs for: {state.get('part_number')}')
    return {**state, 'spec_compliance': True}

def check_dual_use(state: ToolingState) -> ToolingState:
    print('Performing dual-use export control screening for hardened steel.')
    return {**state, 'export_control_check': True}

graph = StateGraph(ToolingState)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', check_dual_use)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
