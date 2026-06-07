from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ImageSoftwareState(TypedDict):
    software_name: str
    license_key: str
    validation_status: bool
    tasks: Annotated[Sequence[str], operator.add]

def validate_license(state: ImageSoftwareState):
    # Simulate license key verification logic
    is_valid = len(state['license_key']) > 10
    return {'validation_status': is_valid}

def perform_install(state: ImageSoftwareState):
    if state['validation_status']:
        return {'tasks': ['License validated', 'Installer initialized', 'Deployment complete']}
    return {'tasks': ['Deployment failed: Invalid License']}

def build_graph():
    graph = StateGraph(ImageSoftwareState)
    graph.add_node('validate', validate_license)
    graph.add_node('install', perform_install)
    graph.add_edge('validate', 'install')
    graph.add_edge('install', END)
    graph.set_entry_point('validate')
    return graph.compile()

graph = build_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'software_name': "",
    'license_key': "",
    'validation_status': False,
    'tasks': []
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
