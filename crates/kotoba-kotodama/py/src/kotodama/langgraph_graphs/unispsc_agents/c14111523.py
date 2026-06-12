from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PrintingState(TypedDict):
    paper_specs: dict
    validation_logs: List[str]
    is_approved: bool

def validate_specs(state: PrintingState):
    logs = []
    specs = state.get('paper_specs', {})
    if specs.get('gsm_weight', 0) < 80:
        logs.append('Insufficient grammage for high-quality output')
    return {'validation_logs': logs, 'is_approved': len(logs) == 0}

def printer_calibration(state: PrintingState):
    return {'validation_logs': state['validation_logs'] + ['Printer ICC profile optimized for media']}

graph = StateGraph(PrintingState)
graph.add_node('validate', validate_specs)
graph.add_node('calibrate', printer_calibration)
graph.add_edge('validate', 'calibrate')
graph.add_edge('calibrate', END)
graph.set_entry_point('validate')
graph = graph.compile()
