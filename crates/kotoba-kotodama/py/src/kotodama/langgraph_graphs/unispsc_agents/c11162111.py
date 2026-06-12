from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MineralProcessState(TypedDict):
    process_steps: Annotated[Sequence[str], operator.add]
    validation_results: dict

def validate_purity(state: MineralProcessState) -> MineralProcessState:
    return {'process_steps': ['purity_verified']}

def execute_refinement(state: MineralProcessState) -> MineralProcessState:
    return {'process_steps': ['refinement_complete']}

graph = StateGraph(MineralProcessState)
graph.add_node('validate', validate_purity)
graph.add_node('execute', execute_refinement)
graph.add_edge('validate', 'execute')
graph.set_entry_point('validate')
graph.add_edge('execute', END)

graph = graph.compile()
