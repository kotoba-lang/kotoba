from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class IndexCardState(TypedDict):
    content: str
    category: str
    is_verified: bool
    validation_log: List[str]

def classify_card(state: IndexCardState) -> IndexCardState:
    state['validation_log'].append('Classifying index card content.')
    state['category'] = 'Standard Filing' if len(state['content']) < 500 else 'Extended Data'
    return state

def verify_quality(state: IndexCardState) -> IndexCardState:
    state['is_verified'] = True
    state['validation_log'].append('Quality check passed for standard office stationery.')
    return state

graph = StateGraph(IndexCardState)
graph.add_node('classify', classify_card)
graph.add_node('verify', verify_quality)
graph.set_entry_point('classify')
graph.add_edge('classify', 'verify')
graph.add_edge('verify', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'content': "",
    'category': "",
    'is_verified': False,
    'validation_log': []
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
