from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    part_number: str
    spec_requirements: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_bearing_specs(state: BearingState) -> dict:
    # Specialized validation logic for bearing load specs
    spec = state['spec_requirements']
    if spec.get('load_rating_dynamic', 0) > 0:
        return {'validation_logs': ['Load specs verified'], 'is_approved': True}
    return {'validation_logs': ['Load specs missing'], 'is_approved': False}

def quality_control_check(state: BearingState) -> dict:
    # Simulated inspection logic for industrial components
    return {'validation_logs': ['ISO tolerance verification complete']}

graph = StateGraph(BearingState)
graph.add_node('validate', validate_bearing_specs)
graph.add_node('qc', quality_control_check)
graph.add_edge('validate', 'qc')
graph.add_edge('qc', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_number': "",
    'spec_requirements': {},
    'validation_logs': [],
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
