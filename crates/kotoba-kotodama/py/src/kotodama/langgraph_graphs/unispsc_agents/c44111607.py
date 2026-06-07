from typing import TypedDict
from langgraph.graph import StateGraph, END
class ProcessState(TypedDict):
    file_type: str
    metadata_valid: bool
    action: str
def validate_check_file(state: ProcessState):
    print(f'Validating file format for {state.get('file_type')}')
    return {'metadata_valid': True}
def execute_filing(state: ProcessState):
    print('Executing filing sequence')
    return {'action': 'filed'}
graph = StateGraph(ProcessState)
graph.add_node('validate', validate_check_file)
graph.add_node('file', execute_filing)
graph.set_entry_point('validate')
graph.add_edge('validate', 'file')
graph.add_edge('file', END)
graph = graph.compile()
