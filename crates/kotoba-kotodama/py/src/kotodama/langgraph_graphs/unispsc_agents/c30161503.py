from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DrywallState(TypedDict):
    order_id: str
    specifications: dict
    approved: bool
    validation_log: List[str]

def validate_drywall_specs(state: DrywallState):
    specs = state.get('specifications', {})
    log = []
    if specs.get('thickness', 0) < 9.5:
        log.append('Thickness below minimum standard')
    return {'validation_log': log, 'approved': len(log) == 0}

graph = StateGraph(DrywallState)
graph.add_node('validate', validate_drywall_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
