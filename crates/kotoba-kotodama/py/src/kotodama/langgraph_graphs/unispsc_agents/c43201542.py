from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class DBState(TypedDict):
    tasks: Annotated[Sequence[str], operator.add]
    status: str

def validate_query(state: DBState) -> DBState:
    return {'tasks': ['query_validated'], 'status': 'valid'}

def execute_optimization(state: DBState) -> DBState:
    return {'tasks': ['optimized'], 'status': 'optimized'}

def route_by_complexity(state: DBState) -> str:
    return 'optimize' if 'complex' in state.get('tasks', []) else END

graph = StateGraph(DBState)
graph.add_node('validate', validate_query)
graph.add_node('optimize', execute_optimization)
graph.set_entry_point('validate')
graph.add_edge('validate', 'optimize')
graph.add_edge('optimize', END)
graph = graph.compile()
