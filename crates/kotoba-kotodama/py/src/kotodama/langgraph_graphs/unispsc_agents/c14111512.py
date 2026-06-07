from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class OfficePaperState(TypedDict):
    paper_id: str
    spec_requirements: dict
    validation_passed: bool
    inspection_logs: List[str]

def validate_paper_spec(state: OfficePaperState) -> OfficePaperState:
    specs = state.get('spec_requirements', {})
    # Specialized logic for paper grade validation
    passed = specs.get('brightness_percentage', 0) >= 80
    state['validation_passed'] = passed
    state['inspection_logs'].append(f'Brightness check passed: {passed}')
    return state

def quality_control_node(state: OfficePaperState) -> OfficePaperState:
    state['inspection_logs'].append('Performing density and moisture content check.')
    return state

graph = StateGraph(OfficePaperState)
graph.add_node('validate', validate_paper_spec)
graph.add_node('qc', quality_control_node)
graph.set_entry_point('validate')
graph.add_edge('validate', 'qc')
graph.add_edge('qc', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'paper_id': "",
    'spec_requirements': {},
    'validation_passed': False,
    'inspection_logs': []
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
