from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PrintingAwlState(TypedDict):
    specs: dict
    validation_log: List[str]
    is_approved: bool

def validate_tool_integrity(state: PrintingAwlState):
    specs = state.get('specs', {})
    if 'tip_diameter' in specs and 'material' in specs:
        state['validation_log'].append('Physical integrity check passed.')
        return {'is_approved': True}
    return {'is_approved': False}

graph = StateGraph(PrintingAwlState)
graph.add_node('validate', validate_tool_integrity)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
