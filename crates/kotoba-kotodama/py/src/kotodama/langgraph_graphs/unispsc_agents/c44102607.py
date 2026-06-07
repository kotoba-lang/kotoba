from typing import TypedDict
from langgraph.graph import StateGraph, END

class WordProcessorState(TypedDict):
    model_number: str
    spec_compliance: bool
    validation_log: list

def validate_specs(state: WordProcessorState):
    log = []
    compliant = True
    if not state.get('model_number'):
        log.append('Missing model number')
        compliant = False
    return {'spec_compliance': compliant, 'validation_log': log}

graph = StateGraph(WordProcessorState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
