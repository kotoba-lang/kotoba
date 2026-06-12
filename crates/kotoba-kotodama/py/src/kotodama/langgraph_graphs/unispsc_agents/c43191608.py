from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class GatewayState(TypedDict):
    request_payload: dict
    security_logs: Annotated[Sequence[str], operator.add]
    validation_result: bool

def validate_request(state: GatewayState) -> dict:
    payload = state.get('request_payload', {})
    is_valid = 'endpoint' in payload and 'token' in payload
    return {'validation_result': is_valid}

def process_gateway_routing(state: GatewayState) -> dict:
    if state['validation_result']:
        return {'security_logs': ['Routing authorized request successfully']}
    else:
        return {'security_logs': ['Routing unauthorized request to blocklist']}

graph = StateGraph(GatewayState)
graph.add_node('validate', validate_request)
graph.add_node('route', process_gateway_routing)
graph.add_edge('validate', 'route')
graph.add_edge('route', END)
graph.set_entry_point('validate')
graph = graph.compile()
