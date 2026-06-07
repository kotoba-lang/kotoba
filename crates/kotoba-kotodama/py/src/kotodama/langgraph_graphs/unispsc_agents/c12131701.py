from typing import TypedDict, List, Annotated
import operator
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    material_code: str
    purity_level: float
    safety_check_passed: bool
    validation_log: Annotated[List[str], operator.add]

def validate_composition(state: CatalystState):
    purity = state.get('purity_level', 0.0)
    if purity >= 99.9:
        return {'safety_check_passed': True, 'validation_log': ['High purity verified']}
    return {'safety_check_passed': False, 'validation_log': ['Purity threshold not met']}

def route_by_safety(state: CatalystState):
    return 'check' if not state['safety_check_passed'] else END

builder = StateGraph(CatalystState)
builder.add_node('check', validate_composition)
builder.set_entry_point('check')
builder.add_edge('check', END)
graph = builder.compile()
