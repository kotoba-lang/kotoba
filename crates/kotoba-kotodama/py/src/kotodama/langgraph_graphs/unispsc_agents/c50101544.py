import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END

class BeanProcurementState(TypedDict):
    order_details: dict
    compliance_check: bool
    final_report: str

def validate_shelf_life(state: BeanProcurementState):
    expiry = state['order_details'].get('expiry_date')
    is_compliant = expiry is not None and len(expiry) > 0
    return {'compliance_check': is_compliant}

def generate_procurement_report(state: BeanProcurementState):
    status = 'APPROVED' if state['compliance_check'] else 'REJECTED'
    return {'final_report': f'Procurement status for batch: {status}'}

graph = StateGraph(BeanProcurementState)
graph.add_node('validate_shelf_life', validate_shelf_life)
graph.add_node('generate_procurement_report', generate_procurement_report)
graph.set_entry_point('validate_shelf_life')
graph.add_edge('validate_shelf_life', 'generate_procurement_report')
graph.add_edge('generate_procurement_report', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'order_details': {},
    'compliance_check': False,
    'final_report': ""
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
