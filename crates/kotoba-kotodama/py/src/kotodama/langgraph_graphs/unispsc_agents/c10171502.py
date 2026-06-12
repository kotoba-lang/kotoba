from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class GrainProcessingState(TypedDict):
    raw_input: dict
    refined_output: dict
    alerts: Annotated[list[str], operator.add]

def filter_impurities(state: GrainProcessingState):
    # Simulate high-precision sorting logic
    return {'refined_output': {'status': 'processed', 'purity': 0.999}}

def validate_output(state: GrainProcessingState):
    if state['refined_output'].get('purity', 0) < 0.99:
        return {'alerts': ['Low purity detected']}
    return {}

graph = StateGraph(GrainProcessingState)
graph.add_node('sort', filter_impurities)
graph.add_node('validate', validate_output)
graph.set_entry_point('sort')
graph.add_edge('sort', 'validate')
graph.add_edge('validate', END)
graph = graph.compile()
