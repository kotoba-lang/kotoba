from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class InferenceState(TypedDict):
    input_data: str
    model_config: dict
    processing_steps: Annotated[List[str], operator.add]
    status: str

def validate_data(state: InferenceState) -> InferenceState:
    return {"processing_steps": ["Validation Passed"], "status": "READY"}

def execute_inference(state: InferenceState) -> InferenceState:
    return {"processing_steps": ["Inference Executed"], "status": "COMPLETED"}

builder = StateGraph(InferenceState)
builder.add_node("validate", validate_data)
builder.add_node("infer", execute_inference)
builder.add_edge("validate", "infer")
builder.add_edge("infer", END)
builder.set_entry_point("validate")
graph = builder.compile()
