from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class AnakinraState(TypedDict):
    batch_id: str
    temp_log: List[float]
    is_compliant: bool

async def check_cold_chain(state: AnakinraState):
    avg_temp = sum(state['temp_log']) / len(state['temp_log'])
    is_compliant = 2.0 <= avg_temp <= 8.0
    return {'is_compliant': is_compliant}

async def validate_batch(state: AnakinraState):
    return {'is_compliant': state['is_compliant'] and state['batch_id'].startswith('ANK')}

graph = StateGraph(AnakinraState)
graph.add_node('cold_chain', check_cold_chain)
graph.add_node('validation', validate_batch)
graph.set_entry_point('cold_chain')
graph.add_edge('cold_chain', 'validation')
graph.add_edge('validation', END)
graph = graph.compile()
