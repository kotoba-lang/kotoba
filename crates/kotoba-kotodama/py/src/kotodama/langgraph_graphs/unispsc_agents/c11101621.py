from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SandState(TypedDict):
    sieve_data: dict
    moisture: float
    status: str
    logs: Annotated[Sequence[str], operator.add]

def validate_sand_spec(state: SandState) -> SandState:
    moisture = state.get('moisture', 0)
    if moisture > 5.0:
        return {'status': 'REJECTED_MOISTURE_HIGH', 'logs': ['Moisture exceeds threshold']}
    return {'status': 'VALIDATED', 'logs': ['Specifications checked against ASTM standards']}

def process_sand_logistics(state: SandState) -> SandState:
    return {'status': 'READY_FOR_SHIPPING', 'logs': ['Logistics routes calculated']}

graph = StateGraph(SandState)
graph.add_node('validate', validate_sand_spec)
graph.add_node('logistics', process_sand_logistics)
graph.add_edge('validate', 'logistics')
graph.add_edge('logistics', END)
graph.set_entry_point('validate')
graph = graph.compile()
