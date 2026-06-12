from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class StampProcessState(TypedDict):
    model_number: str
    validation_passed: bool
    log: List[str]

def validate_stamp(state: StampProcessState):
    model = state.get('model_number', '')
    success = len(model) > 5 and model.isalnum()
    return {'validation_passed': success, 'log': [f'Validation: {success}']}

def perform_init(state: StampProcessState):
    return {'log': state['log'] + ['Initializing stamp mechanism']}

graph = StateGraph(StampProcessState)
graph.add_node('validate', validate_stamp)
graph.add_node('initialize', perform_init)
graph.set_entry_point('validate')
graph.add_edge('validate', 'initialize')
graph.add_edge('initialize', END)
graph = graph.compile()
