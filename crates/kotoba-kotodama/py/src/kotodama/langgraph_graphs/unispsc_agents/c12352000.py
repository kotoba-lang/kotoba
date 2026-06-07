from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    commodity_code: str
    purity_level: float
    safety_check_passed: bool
    log: List[str]

def validate_purity(state: ChemicalState):
    purity = state.get('purity_level', 0.0)
    if purity >= 99.9:
        return {'safety_check_passed': True, 'log': state.get('log', []) + ['Purity validation passed']}
    return {'safety_check_passed': False, 'log': state.get('log', []) + ['Purity too low']}

def process_safety_check(state: ChemicalState):
    if state['safety_check_passed']:
        return 'secure_storage'
    return 'flag_for_review'

graph = StateGraph(ChemicalState)
graph.add_node('validate', validate_purity)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', process_safety_check, {'secure_storage': END, 'flag_for_review': END})
graph = graph.compile()
