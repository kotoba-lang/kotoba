from typing import TypedDict
from langgraph.graph import StateGraph, END

class LenograstimState(TypedDict):
    temperature_log: list
    expiry_check: bool
    compliance_validated: bool

def validate_cold_chain(state: LenograstimState):
    # Simulate cold chain validation logic
    temp_ok = all(t <= 8.0 for t in state['temperature_log'])
    print(f'Temperature criteria met: {temp_ok}')
    return {'compliance_validated': temp_ok}

def verify_regulatory_docs(state: LenograstimState):
    # Simulate GMP and batch documentation check
    return {'expiry_check': True}

graph = StateGraph(LenograstimState)
graph.add_node('cold_chain', validate_cold_chain)
graph.add_node('regulatory', verify_regulatory_docs)
graph.set_entry_point('cold_chain')
graph.add_edge('cold_chain', 'regulatory')
graph.add_edge('regulatory', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'temperature_log': [],
    'expiry_check': False,
    'compliance_validated': False
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
