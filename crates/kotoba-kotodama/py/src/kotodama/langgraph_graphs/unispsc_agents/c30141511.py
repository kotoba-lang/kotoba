from typing import TypedDict
from langgraph.graph import StateGraph, END

class WindowFilmState(TypedDict):
    film_specs: dict
    validation_results: list

def validate_film_specs(state: WindowFilmState):
    specs = state.get('film_specs', {})
    results = []
    if specs.get('thickness', 0) < 50: results.append('Insufficient thickness')
    return {'validation_results': results}

def check_compliance(state: WindowFilmState):
    return {'validation_results': state['validation_results'] + ['Compliance Checked']}

graph = StateGraph(WindowFilmState)
graph.add_node('validate', validate_film_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
