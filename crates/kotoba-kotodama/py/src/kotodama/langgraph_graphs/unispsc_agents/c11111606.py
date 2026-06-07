from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class NickelState(TypedDict):
    assay_data: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_nickel_purity(state: NickelState):
    purity = state['assay_data'].get('nickel_content_percent', 0)
    if purity >= 95.0:
        return {'validation_log': ['High purity verified'], 'is_approved': True}
    return {'validation_log': ['Purity below threshold'], 'is_approved': False}

def check_sanctions(state: NickelState):
    origin = state['assay_data'].get('origin_certification', '')
    if origin in ['CertifiedSafeZone']:
        return {'validation_log': ['Origin verified against sanctions list']}
    return {'validation_log': ['Origin requires manual review'], 'is_approved': False}

graph = StateGraph(NickelState)
graph.add_node('purity_check', validate_nickel_purity)
graph.add_node('sanctions_check', check_sanctions)
graph.set_entry_point('purity_check')
graph.add_edge('purity_check', 'sanctions_check')
graph.add_edge('sanctions_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'assay_data': {},
    'validation_log': [],
    'is_approved': False
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
