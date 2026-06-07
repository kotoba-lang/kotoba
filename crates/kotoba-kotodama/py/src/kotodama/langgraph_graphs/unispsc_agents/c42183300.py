from typing import TypedDict
from langgraph.graph import StateGraph, END

class ENTUnitState(TypedDict):
    part_number: str
    compliance_checked: bool
    needs_sterilization: bool

def validate_part(state: ENTUnitState) -> ENTUnitState:
    print(f'Validating medical part: {state["part_number"]}')
    state['compliance_checked'] = True
    return state

def check_sterilization(state: ENTUnitState) -> ENTUnitState:
    if state.get('needs_sterilization', False):
        print('Verification: Sterilization protocol required.')
    return state

graph = StateGraph(ENTUnitState)
graph.add_node('validate', validate_part)
graph.add_node('sterilization', check_sterilization)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sterilization')
graph.add_edge('sterilization', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_number': "",
    'compliance_checked': False,
    'needs_sterilization': False
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
