from typing import TypedDict
from langgraph.graph import StateGraph, END
class DoorState(TypedDict):
    part_number: str
    quality_score: float
    inspection_passed: bool
def validate_physical_spec(state: DoorState):
    print(f'Validating door component for {state.get('part_number')}')
    return {'inspection_passed': True}
def perform_stress_test(state: DoorState):
    print('Executing hinge and impact stress testing protocols')
    return {'quality_score': 95.0}
graph = StateGraph(DoorState)
graph.add_node('validate', validate_physical_spec)
graph.add_node('stress_test', perform_stress_test)
graph.set_entry_point('validate')
graph.add_edge('validate', 'stress_test')
graph.add_edge('stress_test', END)
graph = graph.compile()
