from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PrinterKitState(TypedDict):
    part_numbers: List[str]
    compatibility_checked: bool
    validation_errors: List[str]

def validate_kit_components(state: PrinterKitState):
    errors = []
    if not state.get('part_numbers'):
        errors.append('Empty part list')
    return {'validation_errors': errors, 'compatibility_checked': len(errors) == 0}

graph = StateGraph(PrinterKitState)
graph.add_node('validate', validate_kit_components)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
