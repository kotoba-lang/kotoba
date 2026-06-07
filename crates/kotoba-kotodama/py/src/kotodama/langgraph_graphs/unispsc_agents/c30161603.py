from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class CofferState(TypedDict):
    spec_data: dict
    validation_errors: List[str]
    approved: bool

def validate_security_rating(state: CofferState):
    errors = []
    if 'rating' not in state['spec_data']:
        errors.append('Missing security rating.')
    return {'validation_errors': errors}

def check_dimensions(state: CofferState):
    # Business logic for industrial safe procurement
    if state['spec_data'].get('weight', 0) > 500:
        print('Logistics validation: Heavy equipment handling required.')
    return {'approved': len(state['validation_errors']) == 0}

workflow = StateGraph(CofferState)
workflow.add_node('validate', validate_security_rating)
workflow.add_node('dimension_check', check_dimensions)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'dimension_check')
workflow.add_edge('dimension_check', END)
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
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
