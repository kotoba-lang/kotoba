from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class FontState(TypedDict):
    font_files: List[str]
    license_type: str
    validation_errors: List[str]
    approved: bool

def validate_font_format(state: FontState):
    errors = []
    for f in state['font_files']:
        if not f.endswith(('.otf', '.ttf', '.woff2')):
            errors.append(f'Invalid format: {f}')
    return {'validation_errors': errors}

def check_license(state: FontState):
    if state['license_type'] not in ['EULA', 'Corporate', 'OpenSource']:
        return {'approved': False}
    return {'approved': True}

graph = StateGraph(FontState)
graph.add_node('validate', validate_font_format)
graph.add_node('license', check_license)
graph.set_entry_point('validate')
graph.add_edge('validate', 'license')
graph.add_edge('license', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'font_files': [],
    'license_type': "",
    'validation_errors': [],
    'approved': False
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
