from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PumpState(TypedDict):
    pump_material: str
    flow_accuracy: float
    food_certified: bool
    validation_log: List[str]

def validate_material(state: PumpState):
    valid = state['pump_material'] in ['Food Grade Polypropylene', 'Stainless Steel 304']
    return {'validation_log': [f'Material validation: {valid}']}

def check_compliance(state: PumpState):
    status = 'Pass' if state['food_certified'] and state['flow_accuracy'] > 0.95 else 'Fail'
    return {'validation_log': state['validation_log'] + [f'Compliance: {status}']}

graph_builder = StateGraph(PumpState)
graph_builder.add_node('validate', validate_material)
graph_builder.add_node('compliance', check_compliance)
graph_builder.set_entry_point('validate')
graph_builder.add_edge('validate', 'compliance')
graph_builder.add_edge('compliance', END)
graph = graph_builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'pump_material': "",
    'flow_accuracy': 0.0,
    'food_certified': False,
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
