from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ChemicalIngestState(TypedDict):
    cas_number: str
    safety_clearance: bool
    compliance_tags: List[str]
    log: Annotated[list, add_messages]

def validate_cas(state: ChemicalIngestState):
    # Simulate rigid CAS database lookup
    if not state.get('cas_number'):
        return {'compliance_tags': ['INVALID_CAS'], 'safety_clearance': False}
    return {'compliance_tags': ['CAS_VERIFIED'], 'safety_clearance': True}

def process_hazard_protocols(state: ChemicalIngestState):
    if not state['safety_clearance']:
        return {'log': ['Safety clearance failed, halting process.']}
    return {'log': ['Hazard protocols verified, proceeding to secure staging.']}

graph = StateGraph(ChemicalIngestState)
graph.add_node('validate', validate_cas)
graph.add_node('hazards', process_hazard_protocols)
graph.add_edge('validate', 'hazards')
graph.add_edge('hazards', END)
graph.set_entry_point('validate')
graph = graph.compile()
