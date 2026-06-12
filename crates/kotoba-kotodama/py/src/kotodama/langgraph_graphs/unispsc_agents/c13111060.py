from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class CatalystState(TypedDict):
    batch_id: str
    specs: dict
    validation_passed: bool
    log: Annotated[Sequence[str], add_messages]

def validate_catalyst_specs(state: CatalystState):
    # Simulate specialized chemical property validation
    passed = state['specs'].get('thermal_stability', 0) > 800
    return {'validation_passed': passed, 'log': ['Validation checked for batch ' + state['batch_id']]}

def process_refining_workflow(state: CatalystState):
    if state['validation_passed']:
        return 'ready_for_dispatch'
    return 'flag_for_quality_review'

workflow = StateGraph(CatalystState)
workflow.add_node('validator', validate_catalyst_specs)
workflow.set_entry_point('validator')
workflow.add_edge('validator', END)

graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'specs': {},
    'validation_passed': False,
    'log': []
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
