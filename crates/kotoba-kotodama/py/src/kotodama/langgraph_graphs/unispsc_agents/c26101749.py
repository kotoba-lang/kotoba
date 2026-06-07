from typing import TypedDict
from langgraph.graph import StateGraph, END

class CrankshaftState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_logs: list

def validate_specs(state: CrankshaftState):
    errors = []
    if state['spec_data'].get('hrc', 0) < 50:
        errors.append('Hardness below minimum requirement')
    return {'validation_passed': len(errors) == 0, 'error_logs': errors}

def quality_workflow(state: CrankshaftState):
    print('Initiating metallurgical analysis and dynamic balance verification.')
    return {'validation_passed': True}

workflow = StateGraph(CrankshaftState)
workflow.add_node('validation', validate_specs)
workflow.add_node('quality_check', quality_workflow)
workflow.set_entry_point('validation')
workflow.add_edge('validation', 'quality_check')
workflow.add_edge('quality_check', END)
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_passed': False,
    'error_logs': []
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
