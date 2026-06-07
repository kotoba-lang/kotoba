from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class DentalToolState(TypedDict):
    tool_id: str
    quality_checks: List[str]
    is_approved: bool

def validate_material(state: DentalToolState):
    # Business logic for material compliance check
    return {'quality_checks': ['ISO7492_PASSED']}

def verify_sterilization(state: DentalToolState):
    # Logic to verify sterilization protocols
    return {'quality_checks': state['quality_checks'] + ['STERILIZATION_VALIDATED']}

graph = StateGraph(DentalToolState)
graph.add_node('check_material', validate_material)
graph.add_node('check_sterilization', verify_sterilization)
graph.set_entry_point('check_material')
graph.add_edge('check_material', 'check_sterilization')
graph.add_edge('check_sterilization', END)
graph = graph.compile()
