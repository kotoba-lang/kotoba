from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class DataProcessingState(TypedDict):
    input_data: str
    model_config: dict
    processing_logs: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_config(state: DataProcessingState):
    # Simulate config validation
    return {"is_compliant": True, "processing_logs": ["Configuration validated."]}

def execute_computation(state: DataProcessingState):
    # Simulate heavy compute task
    return {"processing_logs": ["Computation cycle complete."]}

graph = StateGraph(DataProcessingState)
graph.add_node("validate", validate_config)
graph.add_node("compute", execute_computation)
graph.set_entry_point("validate")
graph.add_edge("validate", "compute")
graph.add_edge("compute", END)
graph = graph.compile()
