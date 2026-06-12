from typing import TypedDict, List
from langgraph.graph import StateGraph, END
class RFIDState(TypedDict):
    device_specs: dict
    compliance_check: bool
    validation_log: List[str]
def validate_specs(state: RFIDState):
    specs = state.get('device_specs', {})
    valid = 'frequency_range' in specs and 'protocol_standard' in specs
    return {'compliance_check': valid, 'validation_log': ['Specs validated' if valid else 'Missing mandatory specs']}
def finalize_procurement(state: RFIDState):
    return {'validation_log': state['validation_log'] + ['Procurement ready for approval']}
graph = StateGraph(RFIDState)
graph.add_node('validate', validate_specs)
graph.add_node('final', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'final')
graph.add_edge('final', END)
graph = graph.compile()
