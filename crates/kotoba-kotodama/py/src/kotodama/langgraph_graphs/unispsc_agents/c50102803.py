from typing import TypedDict
from langgraph.graph import StateGraph, END

class FrozenFruitState(TypedDict):
    batch_id: str
    temp_log_valid: bool
    passed_inspection: bool

def validate_cold_chain(state: FrozenFruitState):
    state['temp_log_valid'] = True
    return state

def run_quality_check(state: FrozenFruitState):
    state['passed_inspection'] = True
    return state

graph = StateGraph(FrozenFruitState)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('quality_check', run_quality_check)
graph.set_entry_point('validate_cold_chain')
graph.add_edge('validate_cold_chain', 'quality_check')
graph.add_edge('quality_check', END)
graph = graph.compile()
