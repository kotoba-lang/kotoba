from typing import TypedDict
from langgraph.graph import StateGraph, END

class GolfCoverState(TypedDict):
    material: str
    club_type: str
    validation_passed: bool

def validate_material(state: GolfCoverState):
    print('Validating material properties for outdoor durability...')
    return {'validation_passed': state.get('material') in ['leather', 'neoprene', 'polyester']}

def check_fit(state: GolfCoverState):
    print(f'Verifying compatibility for {state.get('club_type')}...')
    return {'validation_passed': True}

workflow = StateGraph(GolfCoverState)
workflow.add_node('validate', validate_material)
workflow.add_node('check_fit', check_fit)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'check_fit')
workflow.add_edge('check_fit', END)
graph = workflow.compile()
