from typing import TypedDict
from langgraph.graph import StateGraph, END

class CameraKitState(TypedDict):
    kit_id: str
    components: list
    validation_passed: bool

def validate_specs(state: CameraKitState):
    # Business logic for camera kit compliance validation
    state['validation_passed'] = len(state.get('components', [])) > 0
    return state

def process_export_check(state: CameraKitState):
    # Dual-use export control workflow
    print('Checking export regulations for high-end optical sensors...')
    return {'validation_passed': state['validation_passed']}

graph = StateGraph(CameraKitState)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', process_export_check)
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph.set_entry_point('validate')
graph = graph.compile()
