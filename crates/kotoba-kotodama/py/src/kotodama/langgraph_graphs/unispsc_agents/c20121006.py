from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SolderingState(TypedDict):
    part_id: str
    solder_profile: dict
    status: str
    quality_score: float

def validate_part(state: SolderingState) -> SolderingState:
    print(f'Validating part: {state.get(part_id)}')
    state['status'] = 'validated'
    return state

def execute_soldering(state: SolderingState) -> SolderingState:
    print(f'Executing soldering with {state.get(solder_profile)}')
    state['status'] = 'soldered'
    state['quality_score'] = 0.98
    return state

workflow = StateGraph(SolderingState)
workflow.add_node('validate', validate_part)
workflow.add_node('solder', execute_soldering)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'solder')
workflow.add_edge('solder', END)
graph = workflow.compile()
