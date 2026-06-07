from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class TentBagState(TypedDict):
    spec_data: dict
    validation_passed: bool
    errors: List[str]

def validate_durability(state: TentBagState):
    specs = state.get('spec_data', {})
    errors = []
    if specs.get('denier', 0) < 600:
        errors.append('Material denier too low for durable tent storage.')
    return {'validation_passed': len(errors) == 0, 'errors': errors}

def finalize_procurement(state: TentBagState):
    print('Procurement specification finalized.')
    return {'validation_passed': True}

graph = StateGraph(TentBagState)
graph.add_node('validate', validate_durability)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
