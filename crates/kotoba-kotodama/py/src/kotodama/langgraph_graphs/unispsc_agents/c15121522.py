from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AerospaceTitaniumState(TypedDict):
    material_grade: str
    spec_compliance: bool
    inspection_logs: List[str]
    validation_passed: bool

def validate_grade(state: AerospaceTitaniumState) -> AerospaceTitaniumState:
    # Logic to validate Titanium Grade 5 (Ti-6Al-4V) or equivalent aerospace standards
    if state['material_grade'] in ['Grade 5', 'Grade 23']:
        state['validation_passed'] = True
        state['inspection_logs'].append('Grade validation successful')
    else:
        state['validation_passed'] = False
        state['inspection_logs'].append('Grade validation failed')
    return state

def check_compliance(state: AerospaceTitaniumState) -> AerospaceTitaniumState:
    if state['validation_passed']:
        state['spec_compliance'] = True
    return state

graph = StateGraph(AerospaceTitaniumState)
graph.add_node('validate', validate_grade)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_grade': "",
    'spec_compliance': False,
    'inspection_logs': [],
    'validation_passed': False
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
