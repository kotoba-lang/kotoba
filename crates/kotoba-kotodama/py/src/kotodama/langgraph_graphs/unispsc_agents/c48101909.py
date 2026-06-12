from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    specs: dict
    approved: bool
    validation_log: List[str]

def validate_food_safety(state: ProcurementState):
    material = state.get('specs', {}).get('material', '')
    status = True if material in ['stainless_steel', 'borosilicate_glass'] else False
    return {'approved': status, 'validation_log': ['Food safety compliance checked']}

def finalize_procurement(state: ProcurementState):
    return {'validation_log': state['validation_log'] + ['Procurement workflow finalized']}

graph = StateGraph(ProcurementState)
graph.add_node('safety_check', validate_food_safety)
graph.add_node('finalizer', finalize_procurement)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'finalizer')
graph.add_edge('finalizer', END)
graph = graph.compile()
