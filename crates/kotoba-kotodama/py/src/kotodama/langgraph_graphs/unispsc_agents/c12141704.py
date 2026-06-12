from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    catalyst_id: str
    purity_check: bool
    safety_clearance: bool
    processing_steps: List[str]

def validate_purity(state: CatalystState) -> CatalystState:
    state['purity_check'] = True
    state['processing_steps'].append('Purity Verification Completed')
    return state

def check_safety(state: CatalystState) -> CatalystState:
    state['safety_clearance'] = True
    state['processing_steps'].append('Safety Compliance Check Passed')
    return state

builder = StateGraph(CatalystState)
builder.add_node('purity_node', validate_purity)
builder.add_node('safety_node', check_safety)
builder.add_edge('purity_node', 'safety_node')
builder.set_entry_point('purity_node')
builder.add_edge('safety_node', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'catalyst_id': "",
    'purity_check': False,
    'safety_clearance': False,
    'processing_steps': []
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
