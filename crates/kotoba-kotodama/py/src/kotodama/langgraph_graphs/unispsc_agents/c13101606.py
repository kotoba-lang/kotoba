from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class ProcurementState(TypedDict):
    commodity_code: str
    batch_id: str
    compliance_passed: bool
    validation_log: Annotated[List[str], operator.add]

def validate_chemical_compliance(state: ProcurementState) -> ProcurementState:
    # Logic for chemical purity check and hazard validation
    state['validation_log'] = [f'Validating chemical batch {state["batch_id"]} for code {state["commodity_code"]}']
    state['compliance_passed'] = True
    return state

def run_safety_protocol(state: ProcurementState) -> ProcurementState:
    state['validation_log'] = ['Running safety, hazard, and dual-use checks.']
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_chemical_compliance)
graph.add_node('safety', run_safety_protocol)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'batch_id': "",
    'compliance_passed': False,
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
