from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BedpanState(TypedDict):
    specs: dict
    is_compliant: bool
    validation_log: List[str]

def validate_material(state: BedpanState):
    material = state['specs'].get('material', '')
    compliant = material in ['Polypropylene', 'Stainless Steel']
    return {'is_compliant': compliant, 'validation_log': [f'Material {material} valid: {compliant}']}

def check_sanitation(state: BedpanState):
    is_autoclavable = state['specs'].get('autoclavable', False)
    return {'is_compliant': state['is_compliant'] and is_autoclavable, 'validation_log': state['validation_log'] + ['Sanitation check passed']}

graph = StateGraph(BedpanState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_sanitation', check_sanitation)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'check_sanitation')
graph.add_edge('check_sanitation', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'is_compliant': False,
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
