from typing import TypedDict
from langgraph.graph import StateGraph, END

class TitaniumPartState(TypedDict):
    part_id: str
    material_certified: bool
    tolerance_checked: bool
    ndt_passed: bool

def validate_material(state: TitaniumPartState):
    print(f'Verifying material certs for {state['part_id']}')
    return {'material_certified': True}

def perform_ndt(state: TitaniumPartState):
    print('Executing ultrasonic inspection...')
    return {'ndt_passed': True}

graph = StateGraph(TitaniumPartState)
graph.add_node('verify_material', validate_material)
graph.add_node('ndt_inspection', perform_ndt)
graph.set_entry_point('verify_material')
graph.add_edge('verify_material', 'ndt_inspection')
graph.add_edge('ndt_inspection', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'material_certified': False,
    'tolerance_checked': False,
    'ndt_passed': False
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
