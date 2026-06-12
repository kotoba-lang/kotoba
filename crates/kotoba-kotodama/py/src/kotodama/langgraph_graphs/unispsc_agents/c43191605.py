from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class PointerDeviceState(TypedDict):
    device_id: str
    specs: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_specs(state: PointerDeviceState) -> PointerDeviceState:
    specs = state.get('specs', {})
    log = []
    if specs.get('dpi_resolution', 0) < 800:
        log.append('DPI too low for professional use')
    if not specs.get('interface_type'):
        log.append('Missing interface type')
    return {'validation_log': log, 'is_approved': len(log) == 0}

def finalize_order(state: PointerDeviceState) -> PointerDeviceState:
    return {'validation_log': ['Order processed' if state['is_approved'] else 'Order rejected']}

graph = StateGraph(PointerDeviceState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
