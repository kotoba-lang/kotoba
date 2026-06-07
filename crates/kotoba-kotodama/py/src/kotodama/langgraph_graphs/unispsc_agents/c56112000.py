from typing import TypedDict
from langgraph.graph import StateGraph, END

class FurnitureState(TypedDict):
    spec_data: dict
    validation_result: bool
    compliance_report: str

def validate_ergonomics(state: FurnitureState):
    # Business logic for ergonomic validation
    is_valid = state['spec_data'].get('ergonomic_rating', 0) >= 3
    return {'validation_result': is_valid, 'compliance_report': 'Passed' if is_valid else 'Failed'}

def assemble_procurement(state: FurnitureState):
    # Logic for assembly workflow
    return {'compliance_report': 'Ready for sourcing portal'}

graph = StateGraph(FurnitureState)
graph.add_node('ergonomic_check', validate_ergonomics)
graph.add_node('sourcing_setup', assemble_procurement)
graph.add_edge('ergonomic_check', 'sourcing_setup')
graph.add_edge('sourcing_setup', END)
graph.set_entry_point('ergonomic_check')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_result': False,
    'compliance_report': ""
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
