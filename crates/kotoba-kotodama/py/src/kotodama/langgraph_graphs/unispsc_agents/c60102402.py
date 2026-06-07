from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CurriculumState(TypedDict):
    book_title: str
    target_grade: str
    compliance_checked: bool
    validation_errors: List[str]

def validate_curriculum(state: CurriculumState):
    errors = []
    if not state.get('target_grade'):
        errors.append('Target grade missing')
    return {'validation_errors': errors, 'compliance_checked': len(errors) == 0}

def format_output(state: CurriculumState):
    return {'book_title': f'Validated: {state['book_title']}'}

graph = StateGraph(CurriculumState)
graph.add_node('validate', validate_curriculum)
graph.add_node('format', format_output)
graph.add_edge('validate', 'format')
graph.add_edge('format', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'book_title': "",
    'target_grade': "",
    'compliance_checked': False,
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
