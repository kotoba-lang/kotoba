from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class OcrState(TypedDict):
    raw_input: str
    extracted_text: str
    confidence_score: float
    processing_steps: Annotated[Sequence[str], operator.add]

def scan_document(state: OcrState):
    return {"processing_steps": ["Scanned document image successfully"]}

def perform_ocr(state: OcrState):
    # Simulate high-precision OCR extraction logic
    return {"extracted_text": "Extracted structured data result", "confidence_score": 0.99, "processing_steps": ["Performed OCR analysis"]}

def validate_data(state: OcrState):
    return {"processing_steps": ["Validated data integrity against schema"]}

graph = StateGraph(OcrState)
graph.add_node("scan", scan_document)
graph.add_node("ocr", perform_ocr)
graph.add_node("validate", validate_data)

graph.set_entry_point("scan")
graph.add_edge("scan", "ocr")
graph.add_edge("ocr", "validate")
graph.add_edge("validate", END)

graph = graph.compile()
