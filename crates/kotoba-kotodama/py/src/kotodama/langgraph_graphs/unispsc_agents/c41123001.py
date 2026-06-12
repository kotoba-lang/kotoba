from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class DesiccatorState(TypedDict):
    specifications: dict
    validated: bool
    errors: Annotated[list, operator.add]

def validate_vacuum_specs(state: DesiccatorState):
    specs = state.get('specifications', {})
    if specs.get('vacuum_rated') and 'pressure' not in specs:
        return {'errors': ['Missing pressure tolerance for vacuum-rated unit']}
    return {'validated': True}

def final_approval(state: DesiccatorState):
    return {'validated': True}

graph = StateGraph(DesiccatorState)
graph.add_node('validate', validate_vacuum_specs)
graph.add_node('approve', final_approval)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')

graph = graph.compile()
