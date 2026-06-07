from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class FeedProcurementState(TypedDict):
    commodity_code: str
    nutrition_requirements: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_nutrition(state: FeedProcurementState) -> dict:
    logs = [f'Validating nutritional requirements for {state[commodity_code]}']
    compliant = all(value > 0 for value in state['nutrition_requirements'].values())
    return {'validation_logs': logs, 'is_compliant': compliant}

def process_procurement(state: FeedProcurementState) -> dict:
    return {'validation_logs': ['Procurement order processed successfully']}

graph = StateGraph(FeedProcurementState)
graph.add_node('validate', validate_nutrition)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', lambda s: 'process' if s['is_compliant'] else END)
graph.add_edge('process', END)
graph = graph.compile()
