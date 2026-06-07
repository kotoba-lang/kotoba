from typing import TypedDict
from langgraph.graph import StateGraph, END

class InvestmentState(TypedDict):
    material_type: str
    thermal_expansion: float
    validation_passed: bool

def validate_material(state: InvestmentState):
    if state.get('thermal_expansion', 0) > 0:
        return {'validation_passed': True}
    return {'validation_passed': False}

def process_procurement(state: InvestmentState):
    print('Processing procurement for soldering investment.')
    return state

graph = StateGraph(InvestmentState)
graph.add_node('validate', validate_material)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
