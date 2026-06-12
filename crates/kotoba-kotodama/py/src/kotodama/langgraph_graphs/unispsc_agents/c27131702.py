from typing import TypedDict
from langgraph.graph import StateGraph, END

class CylinderAccessoryState(TypedDict):
    part_number: str
    material: str
    tolerance_check: bool

def validate_specs(state: CylinderAccessoryState):
    # Simulated validation logic for pneumatic accessories
    state['tolerance_check'] = True if 'ISO' in state.get('part_number', '') else False
    return state

def approve_procurement(state: CylinderAccessoryState):
    print(f'Processing procurement for {state.get('part_number')}')
    return {'tolerance_check': True}

graph = StateGraph(CylinderAccessoryState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approve_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
