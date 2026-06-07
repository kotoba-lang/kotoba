from typing import TypedDict, Annotated; import operator; from langgraph.graph import StateGraph, END;
class State(TypedDict): input_data: dict; validation_results: Annotated[list, operator.add]; status: str;
def validate_purity(state: State): return {'validation_results': ['Purity checked against USP/EP standards']};
def check_hazmat(state: State): return {'validation_results': ['SDS and dangerous goods protocols verified']};
graph = StateGraph(State);
graph.add_node('validate_purity', validate_purity);
graph.add_node('check_hazmat', check_hazmat);
graph.set_entry_point('validate_purity');
graph.add_edge('validate_purity', 'check_hazmat');
graph.add_edge('check_hazmat', END);
graph = graph.compile()
