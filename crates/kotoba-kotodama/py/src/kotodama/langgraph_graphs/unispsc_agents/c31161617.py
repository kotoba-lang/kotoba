from typing import TypedDict
from langgraph.graph import StateGraph, END
class WingBoltState(TypedDict):
    spec_data: dict
    validation_results: dict
def validate_specs(state: WingBoltState):
    specs = state.get('spec_data', {})
    results = {'is_valid': all(key in specs for key in ['material', 'thread_type'])}
    return {'validation_results': results}
def log_procurement_entry(state: WingBoltState):
    print(f"Processing Procurement for Wing Bolts: {state['validation_results']}")
    return {}
graph = StateGraph(WingBoltState)
graph.add_node("validate", validate_specs)
graph.add_node("log", log_procurement_entry)
graph.set_entry_point("validate")
graph.add_edge("validate", "log")
graph.add_edge("log", END)
graph = graph.compile()
