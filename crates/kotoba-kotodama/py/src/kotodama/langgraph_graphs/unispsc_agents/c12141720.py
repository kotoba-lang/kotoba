from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    batch_id: str
    purity_check: bool
    safety_clearance: bool
    log: List[str]

def validate_purity(state: CatalystState):
    print(f'Validating purity for {state.get(batch_id)}')
    return {'purity_check': True, 'log': ['Purity verified']}

def safety_protocol(state: CatalystState):
    print('Executing safety handling protocol')
    return {'safety_clearance': True, 'log': ['Safety protocols applied']}

graph = StateGraph(CatalystState)
graph.add_node('validate', validate_purity)
graph.add_node('safety', safety_protocol)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
