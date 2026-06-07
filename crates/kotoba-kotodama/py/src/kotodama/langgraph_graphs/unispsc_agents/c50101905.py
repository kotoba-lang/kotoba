from typing import TypedDict
from langgraph.graph import StateGraph, END

class CranberryProductState(TypedDict):
    grade: str
    pesticide_report_exists: bool
    is_fresh: bool
    approved: bool

def validate_quality(state: CranberryProductState):
    # Business logic for cranberry inspection
    if state.get('pesticide_report_exists') and state.get('is_fresh'):
        state['approved'] = True
    else:
        state['approved'] = False
    return state

graph = StateGraph(CranberryProductState)
graph.add_node('inspection', validate_quality)
graph.set_entry_point('inspection')
graph.add_edge('inspection', END)
graph = graph.compile()
