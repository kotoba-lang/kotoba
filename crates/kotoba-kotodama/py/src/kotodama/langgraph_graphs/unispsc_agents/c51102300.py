from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AntiviralState(TypedDict):
    drug_name: str
    regulatory_status: bool
    batch_compliance: bool

def validate_regulatory(state: AntiviralState):
    print(f'Validating regulatory status for {state['drug_name']}')
    return {'regulatory_status': True}

def check_batch(state: AntiviralState):
    print('Verifying batch and GMP data')
    return {'batch_compliance': True}

graph = StateGraph(AntiviralState)
graph.add_node('regulatory', validate_regulatory)
graph.add_node('batch', check_batch)
graph.add_edge('regulatory', 'batch')
graph.add_edge('batch', END)
graph.set_entry_point('regulatory')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'drug_name': "",
    'regulatory_status': False,
    'batch_compliance': False
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
