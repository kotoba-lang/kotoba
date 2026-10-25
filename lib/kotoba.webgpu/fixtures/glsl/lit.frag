#version 300 es

precision highp float;
precision highp int;

struct G {
    mat4x4 vp;
    vec4 sun_dir;
    vec4 sun_col;
    vec4 sky;
    mat4x4 light_vp;
    vec4 light_a;
    vec4 light_b;
    vec4 light_c;
    vec4 light_d;
};
struct VO {
    vec4 clip;
    vec3 n;
    vec3 col;
    vec3 wpos;
    vec3 mat;
};
layout(std140) uniform G_block_0Fragment { G _group_0_binding_0_fs; };

uniform highp sampler2DShadow _group_0_binding_1_fs;

smooth in vec3 _vs2fs_location0;
smooth in vec3 _vs2fs_location1;
smooth in vec3 _vs2fs_location2;
smooth in vec3 _vs2fs_location3;
layout(location = 0) out vec4 _fs2p_location0;

float shadow(vec3 wpos, float ndl) {
    bool local = false;
    bool local_1 = false;
    bool local_2 = false;
    bool local_3 = false;
    float lit = 0.0;
    int dx = -1;
    int dy = 0;
    mat4x4 _e4 = _group_0_binding_0_fs.light_vp;
    vec4 lc = (_e4 * vec4(wpos, 1.0));
    vec3 ndc = (lc.xyz / vec3(lc.w));
    vec2 uv = vec2(((ndc.x * 0.5) + 0.5), (0.5 - (ndc.y * 0.5)));
    if (!((uv.x < 0.0))) {
        local = (uv.x > 1.0);
    } else {
        local = true;
    }
    bool _e33 = local;
    if (!(_e33)) {
        local_1 = (uv.y < 0.0);
    } else {
        local_1 = true;
    }
    bool _e41 = local_1;
    if (!(_e41)) {
        local_2 = (uv.y > 1.0);
    } else {
        local_2 = true;
    }
    bool _e49 = local_2;
    if (!(_e49)) {
        local_3 = (ndc.z > 1.0);
    } else {
        local_3 = true;
    }
    bool _e57 = local_3;
    if (_e57) {
        return 1.0;
    }
    float _e62 = _group_0_binding_0_fs.light_d.y;
    float _e69 = _group_0_binding_0_fs.light_d.z;
    float bias = max((_e62 * (1.0 - ndl)), _e69);
    float texel = _group_0_binding_0_fs.light_d.w;
    bool loop_init = true;
    while(true) {
        if (!loop_init) {
            int _e105 = dx;
            dx = (_e105 + 1);
        }
        loop_init = false;
        int _e79 = dx;
        if ((_e79 <= 1)) {
        } else {
            break;
        }
        {
            dy = -1;
            bool loop_init_1 = true;
            while(true) {
                if (!loop_init_1) {
                    int _e102 = dy;
                    dy = (_e102 + 1);
                }
                loop_init_1 = false;
                int _e84 = dy;
                if ((_e84 <= 1)) {
                } else {
                    break;
                }
                {
                    float _e87 = lit;
                    int _e90 = dx;
                    int _e92 = dy;
                    float _e99 = textureLod(_group_0_binding_1_fs, vec3((uv + (vec2(float(_e90), float(_e92)) * texel)), (ndc.z - bias)), 0.0);
                    lit = (_e87 + _e99);
                }
            }
        }
    }
    float _e107 = lit;
    return (_e107 / 9.0);
}

void main() {
    VO i = VO(gl_FragCoord, _vs2fs_location0, _vs2fs_location1, _vs2fs_location2, _vs2fs_location3);
    vec3 c = vec3(0.0);
    vec3 N = normalize(i.n);
    vec4 _e5 = _group_0_binding_0_fs.sun_dir;
    vec3 L = normalize(-(_e5.xyz));
    float _e12 = _group_0_binding_0_fs.sun_dir.w;
    float _e16 = _group_0_binding_0_fs.sun_col.w;
    float _e20 = _group_0_binding_0_fs.sky.w;
    vec3 eye = vec3(_e12, _e16, _e20);
    vec3 V = normalize((eye - i.wpos));
    vec3 H = normalize((L + V));
    float ndl_1 = max(dot(N, L), 0.0);
    float metallic = clamp(i.mat.x, 0.0, 1.0);
    float rough = clamp(i.mat.y, 0.04, 1.0);
    float emissive = i.mat.z;
    vec4 _e44 = _group_0_binding_0_fs.light_a;
    vec4 _e48 = _group_0_binding_0_fs.sky;
    float _e53 = _group_0_binding_0_fs.light_a.w;
    vec3 amb = mix(_e44.xyz, (_e48.xyz * _e53), ((N.y * 0.5) + 0.5));
    float _e64 = _group_0_binding_0_fs.light_c.x;
    float _e68 = _group_0_binding_0_fs.light_c.y;
    float shininess = mix(_e64, _e68, (1.0 - rough));
    float _e75 = _group_0_binding_0_fs.light_b.x;
    float _e79 = _group_0_binding_0_fs.light_b.y;
    float specStr = mix(_e75, _e79, metallic);
    vec3 specTint = mix(vec3(1.0), i.col, metallic);
    float spec = (pow(max(dot(N, H), 0.0), shininess) * specStr);
    float _e98 = _group_0_binding_0_fs.light_b.w;
    float _e103 = _group_0_binding_0_fs.light_b.z;
    float rim = (pow((1.0 - max(dot(N, V), 0.0)), _e98) * _e103);
    float _e106 = shadow(i.wpos, ndl_1);
    vec4 _e110 = _group_0_binding_0_fs.sun_col;
    float _e116 = _group_0_binding_0_fs.light_c.z;
    float _e121 = _group_0_binding_0_fs.light_c.w;
    vec4 _e131 = _group_0_binding_0_fs.sun_col;
    vec4 _e139 = _group_0_binding_0_fs.sky;
    c = ((((i.col * (amb + ((((ndl_1 * _e110.xyz) * _e116) * (1.0 - (metallic * _e121))) * _e106))) + (((specTint * _e131.xyz) * spec) * _e106)) + (_e139.xyz * rim)) + (i.col * emissive));
    vec3 _e147 = c;
    vec3 _e148 = c;
    c = (_e147 / (_e148 + vec3(1.0)));
    vec3 _e153 = c;
    float _e157 = _group_0_binding_0_fs.light_d.x;
    c = pow(_e153, vec3((1.0 / _e157)));
    vec3 _e162 = c;
    _fs2p_location0 = vec4(_e162, 1.0);
    return;
}

