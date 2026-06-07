from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class MaterialProcessingState(TypedDict):
    material_id: str
    spec_compliance: bool
    validation_log: Annotated[Sequence[str], operator.add]
    process_status: str

def validate_material_specs(state: MaterialProcessingState):
    log = [f"Validating material {state['material_id']} specs."]
    return {"spec_compliance": True, "validation_log": log, "process_status": "Validated"}

def conduct_stress_test(state: MaterialProcessingState):
    log = ["Performing tensile and thermal stress testing."]
    return {"process_status": "StressTested", "validation_log": log}

def finalize_batch(state: MaterialProcessingState):
    return {"process_status": "ReadyForDispatch"}

graph = StateGraph(MaterialProcessingState)
graph.add_node("validate", validate_material_specs)
graph.add_node("test", conduct_stress_test)
graph.add_node("finalize", finalize_batch)
graph.add_edge("validate", "test")
graph.add_edge("test", "finalize")
graph.add_edge("finalize", END)
graph.set_entry_point("validate")
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'spec_compliance': False,
    'validation_log': [],
    'process_status': ""
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
