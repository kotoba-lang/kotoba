from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class GlassDomeState(TypedDict):
    specs: dict
    validation_passed: bool
    errors: List[str]

def validate_dimensions(state: GlassDomeState):
    errs = []
    if state['specs'].get('diameter_mm', 0) <= 0:
        errs.append('Invalid Diameter')
    return {'validation_passed': len(errs) == 0, 'errors': errs}

def check_transparency(state: GlassDomeState):
    return {'validation_passed': state['validation_passed'] and state['specs'].get('transmission', 0) > 0.9}

builder = StateGraph(GlassDomeState)
builder.add_node('validate_dim', validate_dimensions)
builder.add_node('check_optics', check_transparency)
builder.add_edge('validate_dim', 'check_optics')
builder.add_edge('check_optics', END)
builder.set_entry_point('validate_dim')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'validation_passed': False,
    'errors': []
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
