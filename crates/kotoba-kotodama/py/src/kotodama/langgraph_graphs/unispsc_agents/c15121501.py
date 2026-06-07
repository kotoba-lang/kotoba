from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AluminumBarState(TypedDict):
    alloy_grade: str
    dimensions: dict
    inspection_passed: bool
    log: List[str]

def validate_material(state: AluminumBarState):
    grade = state.get('alloy_grade', 'unknown')
    is_valid = grade in ['6061', '7075', '2024']
    return {'inspection_passed': is_valid, 'log': [f'Validation for grade {grade}: {is_valid}']}

def process_machining(state: AluminumBarState):
    if state['inspection_passed']:
        return {'log': state['log'] + ['Material cleared for precision CNC routing']}
    return {'log': state['log'] + ['Material failed validation, halting']}

graph = StateGraph(AluminumBarState)
graph.add_node('validate', validate_material)
graph.add_node('machining', process_machining)
graph.add_edge('validate', 'machining')
graph.add_edge('machining', END)
graph.set_entry_point('validate')
graph = graph.compile()
