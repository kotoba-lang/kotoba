from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class TrussState(TypedDict):
    spec_data: dict
    validation_passed: bool
    errors: List[str]

def validate_load_specs(state: TrussState):
    load = state['spec_data'].get('load_capacity')
    if not load or load <= 0:
        return {'validation_passed': False, 'errors': ['Invalid load capacity']}
    return {'validation_passed': True}

def structural_compliance(state: TrussState):
    if 'CAD_verified' not in state['spec_data']:
        return {'validation_passed': False, 'errors': ['CAD drawing missing verification']}
    return {'validation_passed': True}

graph = StateGraph(TrussState)
graph.add_node('load_check', validate_load_specs)
graph.add_node('cad_check', structural_compliance)
graph.set_entry_point('load_check')
graph.add_edge('load_check', 'cad_check')
graph.add_edge('cad_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
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
