from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class FireproofingState(TypedDict):
    product_name: str
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_materials(state: FireproofingState):
    specs = state['spec_data']
    passed = 'UL_Certification' in specs and specs['Flame_Spread_Rating'] < 25
    return {'validation_passed': passed, 'compliance_report': 'Passed' if passed else 'Non-compliant'}

def generate_safety_doc(state: FireproofingState):
    return {'compliance_report': f'Safety documentation generated for {state[product_name]}'}

graph = StateGraph(FireproofingState)
graph.add_node('validation', validate_materials)
graph.add_node('documentation', generate_safety_doc)
graph.set_entry_point('validation')
graph.add_edge('validation', 'documentation')
graph.add_edge('documentation', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'product_name': "",
    'spec_data': {},
    'validation_passed': False,
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
