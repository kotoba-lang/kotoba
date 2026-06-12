from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    device_id: str
    specifications: dict
    is_compliant: bool
    validation_log: List[str]

def validate_medical_specs(state: ProcessingState):
    specs = state.get('specifications', {})
    log = []
    if specs.get('temp_control_precision', 0) > 0.5:
        log.append('Temperature precision failure')
    state['is_compliant'] = (len(log) == 0)
    state['validation_log'] = log
    return state

def check_regulatory(state: ProcessingState):
    if not state.get('specifications', {}).get('mdr_certified', False):
        state['is_compliant'] = False
        state['validation_log'].append('MDR certification missing')
    return state

graph = StateGraph(ProcessingState)
graph.add_node('validate_specs', validate_medical_specs)
graph.add_node('check_regulatory', check_regulatory)
graph.set_entry_point('validate_specs')
graph.add_edge('validate_specs', 'check_regulatory')
graph.add_edge('check_regulatory', END)
graph = graph.compile()
