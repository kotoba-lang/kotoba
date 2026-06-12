from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ImageProcessState(TypedDict):
    file_path: str
    task_type: str
    ocr_required: bool
    metadata: dict
    status: str

def validate_format(state: ImageProcessState):
    # Simplified validation logic
    return {"status": "format_validated"}

def perform_ocr(state: ImageProcessState):
    if state.get("ocr_required"):
        return {"status": "ocr_completed"}
    return {"status": "ocr_skipped"}

def finalize_process(state: ImageProcessState):
    return {"status": "processed"}

builder = StateGraph(ImageProcessState)
builder.add_node("validate", validate_format)
builder.add_node("ocr", perform_ocr)
builder.add_node("finalize", finalize_process)
builder.add_edge("validate", "ocr")
builder.add_edge("ocr", "finalize")
builder.add_edge("finalize", END)
builder.set_entry_point("validate")
graph = builder.compile()
