from typing import TypedDict
from langgraph.graph import StateGraph, END

class RetractorState(TypedDict):
    instrument_id: str
    material_certified: bool
    sterilization_validated: bool
    quality_status: str

def validate_material(state: RetractorState):
    state['material_certified'] = True
    return {'material_certified': True}

def validate_sterilization(state: RetractorState):
    state['sterilization_validated'] = True
    state['quality_status'] = 'Approved'
    return {'sterilization_validated': True, 'quality_status': 'Approved'}

graph = StateGraph(RetractorState)
graph.add_node('material_check', validate_material)
graph.add_node('sterilization_check', validate_sterilization)
graph.add_edge('material_check', 'sterilization_check')
graph.add_edge('sterilization_check', END)
graph.set_entry_point('material_check')
graph = graph.compile()
