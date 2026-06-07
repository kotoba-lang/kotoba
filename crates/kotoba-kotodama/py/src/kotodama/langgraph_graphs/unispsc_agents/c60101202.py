from langgraph.graph import StateGraph, END
from typing import TypedDict, List
class IncentiveChartState(TypedDict):
    theme: str
    slots: int
    paper_stock: str
    approval_status: bool
def validate_theme(state: IncentiveChartState):
    state['approval_status'] = 'Bible' in state['theme']
    return state
def check_material(state: IncentiveChartState):
    return {'approval_status': state['approval_status'] and state['paper_stock'] == 'cardstock'}
builder = StateGraph(IncentiveChartState)
builder.add_node('validate_theme', validate_theme)
builder.add_node('check_material', check_material)
builder.set_entry_point('validate_theme')
builder.add_edge('validate_theme', 'check_material')
builder.add_edge('check_material', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'theme': "",
    'slots': 0,
    'paper_stock': "",
    'approval_status': False
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
