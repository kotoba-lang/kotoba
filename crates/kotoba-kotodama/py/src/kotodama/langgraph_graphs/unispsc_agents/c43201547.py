from typing import TypedDict, Annotated, List
import operator
from langgraph.graph import StateGraph, END

class OCRState(TypedDict):
    document_path: str
    ocr_results: Annotated[List[str], operator.add]
    is_validated: bool
    error_log: Annotated[List[str], operator.add]

def node_preprocess_image(state: OCRState):
    # Simulate image pre-processing logic
    return {"ocr_results": ["preprocessed_image_ready"]}

def node_perform_ocr(state: OCRState):
    # Simulate OCR engine invocation
    return {"ocr_results": ["extracted_text_block_1"]}

def node_validate_quality(state: OCRState):
    # Simulate validation of output quality
    return {"is_validated": True}

workflow = StateGraph(OCRState)
workflow.add_node("preprocess", node_preprocess_image)
workflow.add_node("ocr", node_perform_ocr)
workflow.add_node("validate", node_validate_quality)

workflow.set_entry_point("preprocess")
workflow.add_edge("preprocess", "ocr")
workflow.add_edge("ocr", "validate")
workflow.add_edge("validate", END)

graph = workflow.compile()
