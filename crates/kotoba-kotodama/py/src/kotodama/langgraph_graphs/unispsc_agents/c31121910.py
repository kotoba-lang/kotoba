from typing import TypedDict
from langgraph.graph import StateGraph, END

class MoldState(TypedDict):
    specs: dict
    validated: bool
    error: str

def validate_material(state: MoldState):
    content = state.get('specs', {})
    if 'ratio' in content and 'tolerance' in content:
        return {'validated': True}
    return {'validated': False, 'error': 'Missing material specs'}

def process_casting(state: MoldState):
    print('Processing Copper-Graphite Casting...')
    return {'validated': True}

graph = StateGraph(MoldState)
graph.add_node('validate', validate_material)
graph.add_node('process', process_casting)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
