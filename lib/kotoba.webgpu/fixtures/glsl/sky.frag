#version 300 es

precision highp float;
precision highp int;

struct SU {
    vec4 zenith;
    vec4 ground;
};
struct VO {
    vec4 clip;
    vec2 uv;
};
layout(std140) uniform SU_block_0Fragment { SU _group_0_binding_0_fs; };

smooth in vec2 _vs2fs_location0;
layout(location = 0) out vec4 _fs2p_location0;

void main() {
    VO i = VO(gl_FragCoord, _vs2fs_location0);
    vec4 _e3 = _group_0_binding_0_fs.zenith;
    vec4 _e6 = _group_0_binding_0_fs.ground;
    _fs2p_location0 = mix(_e3, _e6, i.uv.y);
    return;
}

