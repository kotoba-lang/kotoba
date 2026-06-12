from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class DocumentState(TypedDict):
    document_id: str
    workflow_steps: Annotated[Sequence[str], operator.add]
    status: str

def validate_metadata(state: DocumentState) -> DocumentState:
    print(f'Validating metadata for {state[document_id]}')
    return {status: 'metadata_validated'}

def execute_workflow(state: DocumentState) -> DocumentState:
    print(f'Executing workflow for {state[document_id]}')
    return {status: 'workflow_completed'}

graph = StateGraph(DocumentState)
graph.add_node('validate', validate_metadata)
graph.add_node('execute', execute_workflow)
graph.set_entry_point('validate')
graph.add_edge('validate', 'execute')
graph.add_edge('execute', END)
graph = graph.compile()
