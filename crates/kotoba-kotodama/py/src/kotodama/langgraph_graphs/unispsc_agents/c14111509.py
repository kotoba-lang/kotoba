from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class FolderState(TypedDict):
    doc_metadata: dict
    validation_log: Annotated[List[str], add_messages]
    status: str

def validate_folder_specs(state: FolderState):
    metadata = state.get('doc_metadata', {})
    required = ['gsm', 'acid_free']
    logs = [f'Validating: {k}' for k in required if k in metadata]
    return {'validation_log': logs, 'status': 'validated'}

def route_to_archiving(state: FolderState):
    return 'archive'

graph = StateGraph(FolderState)
graph.add_node('validate', validate_folder_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
