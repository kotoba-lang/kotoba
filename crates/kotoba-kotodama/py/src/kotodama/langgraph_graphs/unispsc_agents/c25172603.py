from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BumperState(TypedDict):
    part_number: str
    material_specs: dict
    approved: bool
    validation_log: List[str]

def validate_specs(state: BumperState):
    log = []
    if not state.get('material_specs'):
        log.append('Missing material specs')
    return {'validation_log': log}

def check_approval(state: BumperState):
    return {'approved': len(state['validation_log']) == 0}

graph = StateGraph(BumperState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', check_approval)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
