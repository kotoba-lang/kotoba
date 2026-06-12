from typing import TypedDict
from langgraph.graph import StateGraph, END

class ArtProcurementState(TypedDict):
    item_id: str
    provenance: bool
    condition_report: bool
    approved: bool

def verify_provenance(state: ArtProcurementState):
    print('Verifying artwork provenance...')
    return {'provenance': True}

def validate_condition(state: ArtProcurementState):
    print('Validating condition reports...')
    return {'condition_report': True}

def finalize_procurement(state: ArtProcurementState):
    print('Finalizing artwork acquisition...')
    return {'approved': True}

graph = StateGraph(ArtProcurementState)
graph.add_node('verify_provenance', verify_provenance)
graph.add_node('validate_condition', validate_condition)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('verify_provenance')
graph.add_edge('verify_provenance', 'validate_condition')
graph.add_edge('validate_condition', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
