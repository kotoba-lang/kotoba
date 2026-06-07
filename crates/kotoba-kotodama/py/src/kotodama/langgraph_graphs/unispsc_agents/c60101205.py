from typing import TypedDict
from langgraph.graph import StateGraph, END
class PunchcardState(TypedDict):
    card_id: str
    spec_compliance: bool
    approved: bool
def validate_specs(state: PunchcardState):
    state['spec_compliance'] = True
    return {'spec_compliance': True}
def final_review(state: PunchcardState):
    state['approved'] = state['spec_compliance']
    return {'approved': state['approved']}
graph = StateGraph(PunchcardState)
graph.add_node('validate', validate_specs)
graph.add_node('review', final_review)
graph.add_edge('validate', 'review')
graph.add_edge('review', END)
graph.set_entry_point('validate')
graph = graph.compile()
