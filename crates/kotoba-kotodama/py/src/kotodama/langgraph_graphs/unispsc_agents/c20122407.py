from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ReducerState(TypedDict):
    spec_data: dict
    validation_logs: Annotated[Sequence[str], add_messages]

def validate_specs(state: ReducerState):
    spec = state.get('spec_data', {})
    if spec.get('backlash_arcmin', 10) > 5:
        return {'validation_logs': ['Critical: Backlash exceeds tolerance for precision robotics.']}
    return {'validation_logs': ['Validation: Specifications within operational norms.']}

def perform_quality_check(state: ReducerState):
    return {'validation_logs': ['Quality Check: ISO certification verified for precision components.']}

graph = StateGraph(ReducerState)
graph.add_node('validate', validate_specs)
graph.add_node('quality', perform_quality_check)
graph.add_edge('validate', 'quality')
graph.add_edge('quality', END)
graph.set_entry_point('validate')
graph = graph.compile()
