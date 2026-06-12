from langgraph.graph import StateGraph, END
from typing import TypedDict
class DrugState(TypedDict): medicine: str; temp_log: list; valid: bool
def validate_batch(state: DrugState):
    return {'valid': (state.get('medicine') == 'Methylprednisolone' and len(state.get('temp_log', [])) > 0)}
def compliance_check(state: DrugState):
    print('Checking regulatory compliance for medicine...')
    return {'valid': True}
graph = StateGraph(DrugState)
graph.add_node('validate', validate_batch)
graph.add_node('compliance', compliance_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
