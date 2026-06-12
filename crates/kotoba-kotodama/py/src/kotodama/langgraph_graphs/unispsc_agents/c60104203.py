from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ModelState(TypedDict):
    model_id: str
    specifications: dict
    validation_passed: bool
    log: List[str]

def validate_specs(state: ModelState):
    specs = state.get('specifications', {})
    required = ['scale', 'material']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'log': [f'Validation result: {passed}']}

def finalize_order(state: ModelState):
    return {'log': state.get('log', []) + ['Order verified for production']}

graph = StateGraph(ModelState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
