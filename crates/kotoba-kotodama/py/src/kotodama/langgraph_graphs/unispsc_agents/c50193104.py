from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class SoupState(TypedDict):
    product_specs: dict
    compliance_checks: List[str]
    is_approved: bool

def validate_ingredients(state: SoupState):
    items = state['product_specs'].get('ingredients', [])
    valid = all(isinstance(i, str) for i in items)
    state['compliance_checks'].append('ingredients_checked')
    return {'is_approved': valid}

def check_shelf_life(state: SoupState):
    life = state['product_specs'].get('shelf_life', 0)
    state['compliance_checks'].append('shelf_life_verified')
    return {'is_approved': state['is_approved'] and (life > 0)}

graph = StateGraph(SoupState)
graph.add_node('validate', validate_ingredients)
graph.add_node('shelf_life', check_shelf_life)
graph.set_entry_point('validate')
graph.add_edge('validate', 'shelf_life')
graph.add_edge('shelf_life', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'product_specs': {},
    'compliance_checks': [],
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
