from typing import TypedDict
from langgraph.graph import StateGraph, END

class DisplaySpecs(TypedDict):
    resolution: str
    interface: str
    tested: bool

def validate_specs(state: DisplaySpecs):
    state['tested'] = '4K' in state.get('resolution', '')
    return state

def assembly_workflow(state: DisplaySpecs):
    print(f'Configuring display with interface: {state.get("interface")}')
    return state

graph = StateGraph(DisplaySpecs)
graph.add_node('validator', validate_specs)
graph.add_node('assembler', assembly_workflow)
graph.set_entry_point('validator')
graph.add_edge('validator', 'assembler')
graph.add_edge('assembler', END)
graph = graph.compile()
