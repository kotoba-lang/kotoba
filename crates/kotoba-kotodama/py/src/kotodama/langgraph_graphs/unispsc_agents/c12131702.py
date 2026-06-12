from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class ReagentState(TypedDict):
    reagent_id: str
    purity_check: bool
    safety_clearance: bool
    final_approval: bool

def validate_purity(state: ReagentState):
    # Simulated complex analytical validation logic
    print(f'Validating purity for {state['reagent_id']}')
    return {'purity_check': True}

def perform_safety_audit(state: ReagentState):
    print(f'Running dual-use export control audit for {state['reagent_id']}')
    return {'safety_clearance': True}

def finalize_procurement(state: ReagentState):
    approved = state['purity_check'] and state['safety_clearance']
    return {'final_approval': approved}

graph = StateGraph(ReagentState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('safety_audit', perform_safety_audit)
graph.add_node('finalize', finalize_procurement)

graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'safety_audit')
graph.add_edge('safety_audit', 'finalize')
graph.add_edge('finalize', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'reagent_id': "",
    'purity_check': False,
    'safety_clearance': False,
    'final_approval': False
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
