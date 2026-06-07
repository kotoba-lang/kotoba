from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ExtrusionState(TypedDict):
    part_specs: dict
    validation_errors: List[str]
    is_approved: bool

def validate_dimensions(state: ExtrusionState):
    errors = []
    if 'tolerance' not in state['part_specs']: errors.append('Missing tolerance spec')
    return {'validation_errors': errors}

def process_extrusion(state: ExtrusionState):
    is_valid = len(state['validation_errors']) == 0
    return {'is_approved': is_valid}

workflow = StateGraph(ExtrusionState)
workflow.add_node('validator', validate_dimensions)
workflow.add_node('processor', process_extrusion)
workflow.set_entry_point('validator')
workflow.add_edge('validator', 'processor')
workflow.add_edge('processor', END)
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_specs': {},
    'validation_errors': [],
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
