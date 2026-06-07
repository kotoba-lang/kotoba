from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class EndoscopeCaseState(TypedDict):
    case_id: str
    material_certified: bool
    sterilization_validated: bool
    passed_inspection: bool

def validate_material(state: EndoscopeCaseState):
    print(f'Validating material specifications for {state["case_id"]}')
    return {'material_certified': True}

def check_sterilization_compliance(state: EndoscopeCaseState):
    print('Checking sterilization cycle compatibility...')
    return {'sterilization_validated': True}

def final_quality_gate(state: EndoscopeCaseState):
    passed = state['material_certified'] and state['sterilization_validated']
    return {'passed_inspection': passed}

graph = StateGraph(EndoscopeCaseState)
graph.add_node('validate_material', validate_material)
graph.add_node('sterilization_check', check_sterilization_compliance)
graph.add_node('final_gate', final_quality_gate)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'sterilization_check')
graph.add_edge('sterilization_check', 'final_gate')
graph.add_edge('final_gate', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'case_id': "",
    'material_certified': False,
    'sterilization_validated': False,
    'passed_inspection': False
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
