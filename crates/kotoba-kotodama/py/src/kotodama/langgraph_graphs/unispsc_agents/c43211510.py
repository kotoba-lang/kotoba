from typing import TypedDict
from langgraph.graph import StateGraph, END

class TerminalState(TypedDict):
    hardware_id: str
    compatibility_check: bool
    validation_report: str

def validate_terminal_specs(state: TerminalState):
    # Simulate CAD or hardware specification verification logic
    ref_id = state.get('hardware_id', '')
    is_compatible = ref_id.startswith('MF-')
    return {'compatibility_check': is_compatible, 'validation_report': 'Validated' if is_compatible else 'Invalid hardware ID'}

def route_by_validation(state: TerminalState):
    return 'process' if state['compatibility_check'] else END

graph = StateGraph(TerminalState)
graph.add_node('validate', validate_terminal_specs)
graph.add_node('process', lambda s: {'validation_report': 'Integrated into mainframe'})
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation, {'process': 'process', '__end__': END})
graph.add_edge('process', END)
graph = graph.compile()
