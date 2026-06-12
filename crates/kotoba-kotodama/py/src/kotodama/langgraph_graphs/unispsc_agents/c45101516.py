from typing import TypedDict
from langgraph.graph import StateGraph, END

class PrintingPlateState(TypedDict):
    material: str
    depth_check_passed: bool
    validation_log: list

def validate_material(state: PrintingPlateState):
    # Simulate material compliance check for cliché manufacturing
    state['validation_log'].append('Validating steel/polymer composition...')
    return {'depth_check_passed': True}

def conduct_engraving_check(state: PrintingPlateState):
    state['validation_log'].append('Checking engraving depth precision...')
    return {'validation_log': state['validation_log'] + ['Depth within tolerance.']}

graph = StateGraph(PrintingPlateState)
graph.add_node('material_check', validate_material)
graph.add_node('depth_check', conduct_engraving_check)
graph.add_edge('material_check', 'depth_check')
graph.add_edge('depth_check', END)
graph.set_entry_point('material_check')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material': "",
    'depth_check_passed': False,
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
