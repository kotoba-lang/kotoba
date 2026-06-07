from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class CarbonFiberState(TypedDict):
    batch_id: str
    specs: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_specs(state: CarbonFiberState):
    specs = state.get('specs', {})
    if specs.get('tensile_strength_mpa', 0) > 1500:
        return {'validation_logs': ['Tensile strength validated'], 'is_approved': True}
    return {'validation_logs': ['Tensile strength below threshold'], 'is_approved': False}

def update_traceability(state: CarbonFiberState):
    return {'validation_logs': [f'Traceability confirmed for {state.get(batch_id, 'N/A')}']}

graph = StateGraph(CarbonFiberState)
graph.add_node('validate', validate_specs)
graph.add_node('trace', update_traceability)
graph.add_edge('validate', 'trace')
graph.add_edge('trace', END)
graph.set_entry_point('validate')
graph = graph.compile()
