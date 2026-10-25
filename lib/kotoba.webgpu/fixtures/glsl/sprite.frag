#version 300 es

precision highp float;
precision highp int;

struct U {
    vec2 viewport;
    vec2 _p0_;
};
struct VO {
    vec4 clip;
    vec2 uv;
    float shape;
    vec4 color;
};
smooth in vec2 _vs2fs_location0;
smooth in float _vs2fs_location1;
smooth in vec4 _vs2fs_location2;
layout(location = 0) out vec4 _fs2p_location0;

void main() {
    VO i = VO(gl_FragCoord, _vs2fs_location0, _vs2fs_location1, _vs2fs_location2);
    float d = 0.0;
    d = (length(i.uv) - 1.0);
    if ((i.shape > 0.5)) {
        d = (max(abs(i.uv.x), abs(i.uv.y)) - 1.0);
    }
    if ((i.shape > 1.5)) {
        d = (abs((length(i.uv) - 0.7)) - 0.3);
    }
    float _e28 = d;
    float aa = fwidth(_e28);
    float _e31 = d;
    float cov = (1.0 - smoothstep(-(aa), aa, _e31));
    if ((cov <= 0.0)) {
        discard;
    }
    _fs2p_location0 = vec4(i.color.xyz, (i.color.w * cov));
    return;
}

