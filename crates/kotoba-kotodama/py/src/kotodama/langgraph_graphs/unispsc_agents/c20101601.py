from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class FastenerState(TypedDict):
    part_number: str
    material: str
    tensile_data: float
    validation_log: Annotated[list[str], operator.add]

def validate_material(state: FastenerState):
    log = ['Material check passed' if state['material'] in ['Steel', 'Aluminum'] else 'Material invalid']
    return {'validation_log': log}

def validate_tensile(state: FastenerState):
    log = ['Tensile strength exceeds threshold' if state['tensile_data'] > 500 else 'Tensile strength insufficient']
    return {'validation_log': log}

graph = StateGraph(FastenerState)
graph.add_node('material_check', validate_material)
graph.add_node('tensile_check', validate_tensile)
graph.add_edge('material_check', 'tensile_check')
graph.add_edge('tensile_check', END)
graph.set_entry_point('material_check')

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_number': "",
    'material': "",
    'tensile_data': 0.0,
    'validation_log': []
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
