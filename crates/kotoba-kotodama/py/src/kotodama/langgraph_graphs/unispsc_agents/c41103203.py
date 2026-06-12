from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PipetteWasherState(TypedDict):
    spec_sheet: dict
    is_compliant: bool
    validation_log: List[str]

def validate_specs(state: PipetteWasherState):
    specs = state.get('spec_sheet', {})
    log = []
    compliant = True
    if 'flow_rate' not in specs:
        log.append('Missing flow rate specifications')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': log}

graph = StateGraph(PipetteWasherState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
