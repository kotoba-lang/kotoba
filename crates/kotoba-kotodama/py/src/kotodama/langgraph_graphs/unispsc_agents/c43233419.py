from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MultimediaState(TypedDict):
    requirements: dict
    validation_log: List[str]
    is_compliant: bool

def validate_codecs(state: MultimediaState):
    log = state.get('validation_log', [])
    reqs = state.get('requirements', {})
    if 'codecs' in reqs:
        log.append(f'Validated supported codecs: {reqs["codecs"]}')
    return {'validation_log': log, 'is_compliant': True}

def check_compliance(state: MultimediaState):
    return 'compliant' if state['is_compliant'] else 'non_compliant'

graph = StateGraph(MultimediaState)
graph.add_node('validate', validate_codecs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()
