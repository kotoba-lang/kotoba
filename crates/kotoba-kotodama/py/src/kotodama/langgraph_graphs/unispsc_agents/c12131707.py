from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    purity: float
    surface_area: float
    validation_passed: bool
    logs: List[str]

def validate_catalyst(state: CatalystState) -> CatalystState:
    purity = state.get('purity', 0.0)
    area = state.get('surface_area', 0.0)
    passed = purity >= 99.9 and area > 100.0
    return {'validation_passed': passed, 'logs': [f'Validation result: {passed}']}

def process_catalyst(state: CatalystState) -> CatalystState:
    return {'logs': state['logs'] + ['Executing specialized refinement protocol']}

graph = StateGraph(CatalystState)
graph.add_node('validate', validate_catalyst)
graph.add_node('process', process_catalyst)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
