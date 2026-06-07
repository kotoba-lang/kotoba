from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    task_id: str
    specs: dict
    validation_log: Annotated[Sequence[str], operator.add]
    status: str

def validate_payload(state: RobotState):
    payload = state['specs'].get('payload_capacity_kg', 0)
    if payload > 50:
        return {'validation_log': ['Payload exceeds standard safety limits - initiate structural integrity audit.']}
    return {'validation_log': ['Payload within safe operational threshold.']}

def check_certification(state: RobotState):
    certs = state['specs'].get('certifications', [])
    if 'ISO10218' not in certs:
        return {'status': 'CERT_REQUIRED', 'validation_log': ['ISO10218 certification missing.']}
    return {'status': 'APPROVED'}

graph = StateGraph(RobotState)
graph.add_node('validate_payload', validate_payload)
graph.add_node('check_certification', check_certification)
graph.set_entry_point('validate_payload')
graph.add_edge('validate_payload', 'check_certification')
graph.add_edge('check_certification', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'task_id': "",
    'specs': {},
    'validation_log': [],
    'status': ""
}


class _DefaultsWrapper2605231330:
    """Pre-fills missing TypedDict fields before delegating to the compiled graph."""

    __slots__ = ("_inner", "_defaults")

    def __init__(self, inner, defaults):
        self._inner = inner
        self._defaults = defaults

    def _merge(self, input_state):
        if not isinstance(input_state, dict):
            return input_state
        merged = dict(self._defaults)
        merged.update(input_state)
        return merged

    def invoke(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            return self._inner.invoke(merged, **kwargs)
        return self._inner.invoke(merged, config=config, **kwargs)

    async def ainvoke(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            return await self._inner.ainvoke(merged, **kwargs)
        return await self._inner.ainvoke(merged, config=config, **kwargs)

    def stream(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            return self._inner.stream(merged, **kwargs)
        return self._inner.stream(merged, config=config, **kwargs)

    async def astream(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            async for chunk in self._inner.astream(merged, **kwargs):
                yield chunk
            return
        async for chunk in self._inner.astream(merged, config=config, **kwargs):
            yield chunk

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_inner"), name)


graph = _DefaultsWrapper2605231330(graph, _DEFAULTS_2605231330)
