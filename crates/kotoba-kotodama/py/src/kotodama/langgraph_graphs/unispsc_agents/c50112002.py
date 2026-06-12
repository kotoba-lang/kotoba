from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MeatProcurementState(TypedDict):
    temp_log: List[float]
    safety_cert_valid: bool
    approved: bool

def validate_cold_chain(state: MeatProcurementState):
    # Ensure all temperature logs are below -18C
    state['approved'] = all(temp <= -18.0 for temp in state['temp_log'])
    return state

def check_certifications(state: MeatProcurementState):
    # Simulate HACCP and health cert verification
    state['approved'] = state['approved'] and state['safety_cert_valid']
    return state

graph = StateGraph(MeatProcurementState)
graph.add_node('validate_temp', validate_cold_chain)
graph.add_node('verify_certs', check_certifications)
graph.set_entry_point('validate_temp')
graph.add_edge('validate_temp', 'verify_certs')
graph.add_edge('verify_certs', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'temp_log': [],
    'safety_cert_valid': False,
    'approved': False
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
