from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class PrecisionPartState(TypedDict):
    part_id: str
    spec_requirements: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_dimensions(state: PrecisionPartState):
    log = f'Validating dimensions for {state.part_id}'
    return {'validation_log': [log], 'is_approved': True}

def check_material(state: PrecisionPartState):
    log = f'Verifying material grade for {state.part_id}'
    return {'validation_log': [log]}

graph = StateGraph(PrecisionPartState)
graph.add_node('validate', validate_dimensions)
graph.add_node('material', check_material)
graph.set_entry_point('validate')
graph.add_edge('validate', 'material')
graph.add_edge('material', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'spec_requirements': {},
    'validation_log': [],
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
