from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AwardProcurementState(TypedDict):
    item_name: str
    engraving_text: str
    material: str
    approved: bool

def validate_engraving(state: AwardProcurementState):
    if not state.get('engraving_text'):
        return {'approved': False}
    return {'approved': True}

def process_award(state: AwardProcurementState):
    print(f'Processing trophy: {state.get('item_name')}')
    return state

graph = StateGraph(AwardProcurementState)
graph.add_node('validate', validate_engraving)
graph.add_node('process', process_award)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
