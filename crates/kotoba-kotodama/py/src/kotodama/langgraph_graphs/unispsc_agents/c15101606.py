from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MiningState(TypedDict):
    cutter_id: str
    material_type: str
    status: str
    inspection_log: List[str]

def validate_cutter(state: MiningState):
    log = f'Validating cutter {state[cutter_id]} for {state[material_type]}'
    return {'inspection_log': [log], 'status': 'validated'}

def execute_mining_op(state: MiningState):
    return {'status': 'active'}

graph = StateGraph(MiningState)
graph.add_node('validate', validate_cutter)
graph.add_node('execute', execute_mining_op)
graph.add_edge('validate', 'execute')
graph.add_edge('execute', END)
graph.set_entry_point('validate')
graph = graph.compile()
