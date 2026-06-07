from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class GearboxState(TypedDict):
    spec_data: dict
    validation_logs: Annotated[List[str], add_messages]
    is_compliant: bool

def validate_gearbox_specs(state: GearboxState):
    specs = state.get('spec_data', {})
    logs = []
    compliant = True
    if specs.get('backlash_arcmin', 10) > 5:
        logs.append('Warning: Backlash exceeds precision threshold.')
        compliant = False
    return {'validation_logs': logs, 'is_compliant': compliant}

def route_by_compliance(state: GearboxState):
    return 'compliant' if state['is_compliant'] else 'flag_for_review'

graph = StateGraph(GearboxState)
graph.add_node('validate', validate_gearbox_specs)
graph.add_node('compliant', lambda s: s)
graph.add_node('flag_for_review', lambda s: s)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance)
graph.add_edge('compliant', END)
graph.add_edge('flag_for_review', END)
graph = graph.compile()
