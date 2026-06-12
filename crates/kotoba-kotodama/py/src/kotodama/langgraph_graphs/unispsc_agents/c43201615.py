from typing import TypedDict
from langgraph.graph import StateGraph, END

class DriveBayState(TypedDict):
    model_id: str
    compatibility_checked: bool
    dimension_validated: bool

def check_compatibility(state: DriveBayState):
    print(f'Checking compatibility for {state['model_id']}')
    return {'compatibility_checked': True}

def validate_dimensions(state: DriveBayState):
    print('Validating bay dimensions...')
    return {'dimension_validated': True}

graph = StateGraph(DriveBayState)
graph.add_node('check_comp', check_compatibility)
graph.add_node('val_dims', validate_dimensions)
graph.set_entry_point('check_comp')
graph.add_edge('check_comp', 'val_dims')
graph.add_edge('val_dims', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'model_id': "",
    'compatibility_checked': False,
    'dimension_validated': False
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
