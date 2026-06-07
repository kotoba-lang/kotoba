from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PenSpecState(TypedDict):
    spec_data: dict
    validation_results: List[str]

def validate_ink_safety(state: PenSpecState):
    sds = state['spec_data'].get('sds_url')
    res = 'Valid' if sds else 'Missing SDS'
    return {'validation_results': [res]}

def check_durability(state: PenSpecState):
    dry_time = state['spec_data'].get('drying_time_sec')
    res = 'Fail' if dry_time > 30 else 'Pass'
    return {'validation_results': [res]}

graph = StateGraph(PenSpecState)
graph.add_node('safety_check', validate_ink_safety)
graph.add_node('durability_check', check_durability)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'durability_check')
graph.add_edge('durability_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_results': []
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
