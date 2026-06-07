from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PharmaState(TypedDict):
    drug_name: str
    purity_level: float
    temp_log: List[float]
    is_compliant: bool

def validate_compliance(state: PharmaState):
    compliant = state['purity_level'] >= 0.99 and all(2 <= t <= 8 for t in state['temp_log'])
    return {'is_compliant': compliant}

def check_certification(state: PharmaState):
    return {'is_compliant': state['is_compliant']}

graph = StateGraph(PharmaState)
graph.add_node('validation', validate_compliance)
graph.add_node('cert_check', check_certification)
graph.add_edge('validation', 'cert_check')
graph.add_edge('cert_check', END)
graph.set_entry_point('validation')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'drug_name': "",
    'purity_level': 0.0,
    'temp_log': [],
    'is_compliant': False
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
