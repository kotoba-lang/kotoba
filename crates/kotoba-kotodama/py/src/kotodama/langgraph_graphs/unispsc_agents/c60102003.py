from typing import TypedDict
from langgraph.graph import StateGraph, END

class BookState(TypedDict):
    content_reviewed: bool
    safety_compliant: bool
    formatted: bool

def check_content(state: BookState):
    return {'content_reviewed': True}

def check_safety(state: BookState):
    return {'safety_compliant': True}

def finalize_format(state: BookState):
    return {'formatted': True}

graph = StateGraph(BookState)
graph.add_node('content', check_content)
graph.add_node('safety', check_safety)
graph.add_node('format', finalize_format)

graph.set_entry_point('content')
graph.add_edge('content', 'safety')
graph.add_edge('safety', 'format')
graph.add_edge('format', END)

graph = graph.compile()
