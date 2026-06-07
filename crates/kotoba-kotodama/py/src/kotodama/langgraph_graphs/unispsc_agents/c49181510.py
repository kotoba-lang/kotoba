from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class FoosballState(TypedDict):
    spec: dict
    validation_log: List[str]
    is_compliant: bool

def validate_structural_integrity(state: FoosballState):
    log = state.get('validation_log', [])
    specs = state.get('spec', {})
    if specs.get('weight', 0) < 50:
        log.append('Table weight insufficient for professional use')
    return {'validation_log': log, 'is_compliant': len(log) == 0}

def validate_safety_safety(state: FoosballState):
    log = state.get('validation_log', [])
    if not state.get('spec', {}).get('certified'):
        log.append('Missing safety certification for rod ends')
    return {'validation_log': log}

graph = StateGraph(FoosballState)
graph.add_node('structural_check', validate_structural_integrity)
graph.add_node('safety_check', validate_safety_safety)
graph.set_entry_point('structural_check')
graph.add_edge('structural_check', 'safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()
