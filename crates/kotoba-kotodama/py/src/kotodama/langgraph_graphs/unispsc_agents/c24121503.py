from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PackagingState(TypedDict):
    box_type: str
    dimensions: dict
    is_compliant: bool
    validation_log: List[str]

def validate_specs(state: PackagingState):
    log = []
    compliant = True
    if not state.get('dimensions'):
        log.append('Missing dimensions')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': log}

def process_packaging(state: PackagingState):
    return {'validation_log': state['validation_log'] + ['Processing packaging registration']}

graph = StateGraph(PackagingState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_packaging)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()
