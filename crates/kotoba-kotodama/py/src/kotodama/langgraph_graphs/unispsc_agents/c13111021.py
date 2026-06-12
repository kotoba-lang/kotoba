from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ExtractionState(TypedDict):
    commodity_code: str
    safety_check_passed: bool
    purity_level: float
    log: Annotated[List[str], add_messages]

def validate_safety(state: ExtractionState):
    is_safe = state.get('purity_level', 0) > 95.0
    return {'safety_check_passed': is_safe, 'log': ['Safety check performed', f'Result: {is_safe}']}

def process_extraction_node(state: ExtractionState):
    if state.get('safety_check_passed'):
        return {'log': ['Proceeding with procurement workflow']}
    return {'log': ['Procurement halted: Safety check failed']}

graph = StateGraph(ExtractionState)
graph.add_node('safety', validate_safety)
graph.add_node('process', process_extraction_node)
graph.set_entry_point('safety')
graph.add_edge('safety', 'process')
graph.add_edge('process', END)
graph = graph.compile()
