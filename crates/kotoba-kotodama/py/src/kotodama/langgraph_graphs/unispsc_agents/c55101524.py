from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BookProcurementState(TypedDict):
    isbn: str
    is_verified: bool
    error_log: List[str]

def validate_isbn(state: BookProcurementState):
    isbn = state.get('isbn', '')
    is_valid = len(isbn.replace('-', '')) in [10, 13]
    return {'is_verified': is_valid}

def process_procurement(state: BookProcurementState):
    if not state['is_verified']:
        return {'error_log': ['Invalid ISBN format provided.']}
    return {'error_log': []}

graph = StateGraph(BookProcurementState)
graph.add_node('validate', validate_isbn)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
