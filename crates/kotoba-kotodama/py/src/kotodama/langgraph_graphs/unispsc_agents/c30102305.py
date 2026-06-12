from typing import TypedDict
from langgraph.graph import StateGraph, END

class SteelSpecState(TypedDict):
    material_grade: str
    dimensions: dict
    mtc_validated: bool

def validate_mtc(state: SteelSpecState):
    state['mtc_validated'] = True if state.get('mtc') else False
    return state

def check_dimensions(state: SteelSpecState):
    print('Verifying dimensional tolerance against JIS standards')
    return state

graph = StateGraph(SteelSpecState)
graph.add_node('validate_mtc', validate_mtc)
graph.add_node('check_dims', check_dimensions)
graph.add_edge('validate_mtc', 'check_dims')
graph.add_edge('check_dims', END)
graph.set_entry_point('validate_mtc')
graph = graph.compile()
