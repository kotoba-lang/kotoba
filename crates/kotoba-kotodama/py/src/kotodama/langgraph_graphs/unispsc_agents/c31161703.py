from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class HardwareState(TypedDict):
    specs: dict
    validation_passed: bool
    error_log: List[str]

def validate_blind_nut(state: HardwareState):
    specs = state.get('specs', {})
    errors = []
    if 'grip_range' not in specs: errors.append('Grip range missing')
    if 'thread_size' not in specs: errors.append('Thread size missing')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def process_procurement(state: HardwareState):
    print('Proceeding with blind nut technical validation...')
    return {'validation_passed': True}

graph = StateGraph(HardwareState)
graph.add_node('validate', validate_blind_nut)
graph.add_node('process', process_procurement)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()
