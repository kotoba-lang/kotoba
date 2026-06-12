from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class LubricantState(TypedDict):
    commodity_id: str
    specs: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_viscosity(state: LubricantState):
    log = []
    if state['specs'].get('viscosity_index', 0) < 100:
        log.append('Low viscosity index detected for industrial standard')
    return {'validation_log': log}

def check_compliance(state: LubricantState):
    is_compliant = 'Low viscosity index detected' not in ' '.join(state['validation_log'])
    return {'is_compliant': is_compliant}

graph = StateGraph(LubricantState)
graph.add_node('validate_viscosity', validate_viscosity)
graph.add_node('check_compliance', check_compliance)
graph.set_entry_point('validate_viscosity')
graph.add_edge('validate_viscosity', 'check_compliance')
graph.add_edge('check_compliance', END)

# Compile the graph
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_id': "",
    'specs': {},
    'validation_log': [],
    'is_compliant': False
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
