from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class FontProcurementState(TypedDict):
    font_format: str
    license_type: str
    validation_errors: List[str]

def validate_font_specs(state: FontProcurementState):
    errors = []
    if state['font_format'] not in ['OTF', 'TTF', 'WOFF2']:
        errors.append('Unsupported font format.')
    return {'validation_errors': errors}

def check_license_compliance(state: FontProcurementState):
    if state['license_type'] == 'restricted':
        return {'validation_errors': state['validation_errors'] + ['Restricted license requires legal review']}
    return {'validation_errors': state['validation_errors']}

graph = StateGraph(FontProcurementState)
graph.add_node('validate', validate_font_specs)
graph.add_node('license_check', check_license_compliance)
graph.add_edge('validate', 'license_check')
graph.add_edge('license_check', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'font_format': "",
    'license_type': "",
    'validation_errors': []
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
