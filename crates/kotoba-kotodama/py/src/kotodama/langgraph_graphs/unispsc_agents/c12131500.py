from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    cas_number: str
    purity_level: float
    compliance_checks: List[str]
    approved: bool

def validate_purity(state: ChemicalState):
    # Business logic for purity verification
    is_pure = state['purity_level'] >= 0.99
    return {'approved': is_pure, 'compliance_checks': state['compliance_checks'] + ['purity_validated']}

def check_regulations(state: ChemicalState):
    # Placeholder for dual-use export control checks
    return {'compliance_checks': state['compliance_checks'] + ['export_control_passed']}

builder = StateGraph(ChemicalState)
builder.add_node('validate', validate_purity)
builder.add_node('compliance', check_regulations)
builder.add_edge('validate', 'compliance')
builder.add_edge('compliance', END)
builder.set_entry_point('validate')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'cas_number': "",
    'purity_level': 0.0,
    'compliance_checks': [],
    'approved': False
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
