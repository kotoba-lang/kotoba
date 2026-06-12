from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MiningState(TypedDict):
    equipment_id: str
    spec_requirements: List[str]
    validation_status: str

def validate_equipment(state: MiningState) -> MiningState:
    if not state.get('equipment_id'):
        state['validation_status'] = 'REJECTED: Missing ID'
    else:
        state['validation_status'] = 'PASSED: Verified'
    return state

def process_procurement(state: MiningState) -> MiningState:
    # Simulate specialized procurement workflow for heavy mining machinery
    state['validation_status'] = 'COMPLETED: Procured'
    return state

graph = StateGraph(MiningState)
graph.add_node('validate', validate_equipment)
graph.add_node('procure', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'procure')
graph.add_edge('procure', END)
graph = graph.compile()
