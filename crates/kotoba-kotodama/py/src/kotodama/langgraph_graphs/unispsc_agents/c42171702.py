from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BlanketState(TypedDict):
    specifications: dict
    is_compliant: bool
    validation_log: List[str]

def validate_specs(state: BlanketState):
    specs = state.get('specifications', {})
    logs = []
    compliant = True
    if 'thermal_retention_rating' not in specs:
        logs.append('Missing thermal rating')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': logs}

def finalize_procurement(state: BlanketState):
    return {'validation_log': state['validation_log'] + ['Procurement ready']}

graph = StateGraph(BlanketState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
