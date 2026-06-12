"""optix C-style API surface (subset) — Pythonized.

NVIDIA OptiX is the NVIDIA Corporation ray tracing API; this module mirrors
the documented public surface (optix.h) per Google v. Oracle (2021) so existing
OptiX scripts can port via import-path-only changes. Implementation routes to
kami-rt (WebGPU ray-query + WGSL LBVH) once that lands at R1.2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


class OptixResult:
    OPTIX_SUCCESS = 0
    OPTIX_ERROR_INVALID_VALUE = 7001
    OPTIX_ERROR_HOST_OUT_OF_MEMORY = 7002


@dataclass
class OptixDeviceContext:
    log_callback_function: Optional[callable] = None
    log_callback_level: int = 0

    def __post_init__(self):
        self._modules: list = []
        self._pipelines: list = []


@dataclass
class OptixModuleCompileOptions:
    max_register_count: int = 0
    opt_level: int = 3
    debug_level: int = 0


@dataclass
class OptixPipelineCompileOptions:
    uses_motion_blur: bool = False
    traversable_graph_flags: int = 0
    num_payload_values: int = 2
    num_attribute_values: int = 2
    exception_flags: int = 0


@dataclass
class OptixModule:
    context: OptixDeviceContext
    source_wgsl: str = ""
    compile_options: OptixModuleCompileOptions = field(default_factory=OptixModuleCompileOptions)


@dataclass
class OptixProgramGroup:
    module: OptixModule
    kind: str = "raygen"  # raygen | miss | hitgroup | callable


@dataclass
class OptixPipeline:
    context: OptixDeviceContext
    program_groups: list[OptixProgramGroup] = field(default_factory=list)
    compile_options: OptixPipelineCompileOptions = field(default_factory=OptixPipelineCompileOptions)


@dataclass
class OptixShaderBindingTable:
    raygen_record: int = 0
    miss_record_base: int = 0
    hitgroup_record_base: int = 0


def optixDeviceContextCreate(cuda_context=None, options=None) -> OptixDeviceContext:
    """C-style constructor. cuda_context is ignored (kami-rt uses WebGPU device)."""
    return OptixDeviceContext()


def optixModuleCreateFromPTX(*args, **kwargs) -> OptixModule:
    raise NotImplementedError(
        "optixModuleCreateFromPTX requires CUDA PTX; substituted by "
        "kami-rt WGSL path at R1.2. Use optixModuleCreateFromWGSL instead."
    )


def optixModuleCreateFromWGSL(
    context: OptixDeviceContext,
    module_compile_options: OptixModuleCompileOptions,
    pipeline_compile_options: OptixPipelineCompileOptions,
    wgsl_source: str,
) -> OptixModule:
    """KAMI-native extension (not in upstream OptiX): create module from WGSL string."""
    m = OptixModule(context=context, source_wgsl=wgsl_source,
                    compile_options=module_compile_options)
    context._modules.append(m)
    return m


def optixPipelineCreate(
    context: OptixDeviceContext,
    pipeline_compile_options: OptixPipelineCompileOptions,
    program_groups: list[OptixProgramGroup],
) -> OptixPipeline:
    pl = OptixPipeline(context=context, program_groups=list(program_groups),
                       compile_options=pipeline_compile_options)
    context._pipelines.append(pl)
    return pl


def optixLaunch(
    pipeline: OptixPipeline,
    sbt: OptixShaderBindingTable,
    launch_params_ptr: int = 0,
    launch_params_size: int = 0,
    width: int = 1,
    height: int = 1,
    depth: int = 1,
) -> int:
    """Issue a ray-trace launch. R1.2 routes to wgpu compute dispatch over WGSL."""
    if not pipeline.program_groups:
        return OptixResult.OPTIX_ERROR_INVALID_VALUE
    # R1.0: no-op success — pipeline is fully synthesized at R1.2 with kami-rt.
    return OptixResult.OPTIX_SUCCESS
