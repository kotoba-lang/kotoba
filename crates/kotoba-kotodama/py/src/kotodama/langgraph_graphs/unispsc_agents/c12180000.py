from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class CatalystState(TypedDict):
    batch_id: str
    purity: float
    safety_check: bool
    history: Annotated[List[str], operator.add]

def validate_catalyst(state: CatalystState):
    if state['purity'] >= 99.9:
        return {'safety_check': True, 'history': ['Purity validation passed']}
    return {'safety_check': False, 'history': ['Purity validation failed']}

def record_compliance(state: CatalystState):
    return {'history': ['Compliance record generated']}

builder = StateGraph(CatalystState)
builder.add_node('validate', validate_catalyst)
builder.add_node('record', record_compliance)
builder.add_edge('validate', 'record')
builder.add_edge('record', END)
builder.set_entry_point('validate')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'purity': 0.0,
    'safety_check': False,
    'history': []
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
