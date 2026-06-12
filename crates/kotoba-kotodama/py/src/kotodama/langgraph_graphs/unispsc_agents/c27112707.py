from typing import TypedDict
from langgraph.graph import StateGraph, END

class RouterState(TypedDict):
    specs: dict
    is_compliant: bool
    validation_log: list

def validate_specs(state: RouterState):
    specs = state.get('specs', {})
    log = []
    compliant = True
    if specs.get('power', 0) < 500:
        log.append('Insufficient power for industrial grade')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': log}

def router_routing(state: RouterState):
    return 'process_order' if state['is_compliant'] else 'flag_for_review'

graph = StateGraph(RouterState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
