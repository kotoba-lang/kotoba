from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class CDDeviceState(TypedDict):
    model_id: str
    specs: dict
    is_compliant: bool
    validation_log: List[str]

def validate_specs(state: CDDeviceState):
    specs = state.get('specs', {})
    log = []
    compliant = True
    if 'interface' not in specs:
        compliant = False
        log.append('Missing interface type.')
    return {'is_compliant': compliant, 'validation_log': log}

def finalize_order(state: CDDeviceState):
    return {'validation_log': state['validation_log'] + ['Order ready for procurement']}

graph = StateGraph(CDDeviceState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_order)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
