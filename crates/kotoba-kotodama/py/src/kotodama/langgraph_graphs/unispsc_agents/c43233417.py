from typing import TypedDict
from langgraph.graph import StateGraph, END

class HWRState(TypedDict):
    input_image: str
    extracted_text: str
    accuracy_score: float

def validate_image(state: HWRState):
    # Business logic for image validation
    return {'extracted_text': 'sample'}

def process_ocr(state: HWRState):
    # Business logic for OCR processing
    return {'accuracy_score': 0.98}

graph = StateGraph(HWRState)
graph.add_node('validator', validate_image)
graph.add_node('ocr_engine', process_ocr)
graph.add_edge('validator', 'ocr_engine')
graph.add_edge('ocr_engine', END)
graph.set_entry_point('validator')
graph = graph.compile()
