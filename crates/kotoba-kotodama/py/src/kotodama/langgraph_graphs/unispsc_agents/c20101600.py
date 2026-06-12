from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MiningState(TypedDict):
    part_id: str
    spec_compliance: bool
    inspection_log: List[str]

def validate_mining_part(state: MiningState):
    log = f'Validating durability and certification for {state[part_id]}'
    return {'inspection_log': [log], 'spec_compliance': True}

def route_by_safety(state: MiningState):
    return 'process_mining_order'

graph = StateGraph(MiningState)
graph.add_node('validate', validate_mining_part)
graph.add_node('process_mining_order', lambda s: {'inspection_log': s['inspection_log'] + ['Processing industrial order']})
graph.set_entry_point('validate')
graph.add_edge('validate', 'process_mining_order')
graph.add_edge('process_mining_order', END)

graph = graph.compile()
