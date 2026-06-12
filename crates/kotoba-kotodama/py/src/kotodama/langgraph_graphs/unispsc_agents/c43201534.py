from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class EdgeProcessState(TypedDict):
    task_id: str
    input_data: dict
    processing_steps: Annotated[Sequence[str], operator.add]
    is_optimized: bool

def validate_edge_capability(state: EdgeProcessState):
    print(f'Validating capability for {state[task_id]}')
    return {'processing_steps': ['capability_checked']}

def perform_local_optimization(state: EdgeProcessState):
    print(f'Optimizing workload for {state[task_id]}')
    return {'is_optimized': True, 'processing_steps': ['local_optimization_applied']}

graph = StateGraph(EdgeProcessState)
graph.add_node('validate', validate_edge_capability)
graph.add_node('optimize', perform_local_optimization)
graph.set_entry_point('validate')
graph.add_edge('validate', 'optimize')
graph.add_edge('optimize', END)
graph = graph.compile()
