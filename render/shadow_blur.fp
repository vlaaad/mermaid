#version 140
in mediump vec2 var_uv;
out highp vec4 out_fragColor;
uniform highp sampler2D moments;
uniform fs_uniforms { highp vec4 blur_direction; };
void main() {
    highp vec2 uv=vec2(var_uv.x,1.0-var_uv.y),d=blur_direction.xy;
    highp vec4 v=texture(moments,uv)*.227027027;
    if(blur_direction.z<.5) {
        v+=(texture(moments,uv+d*1.384615385)+texture(moments,uv-d*1.384615385))*.316216216;
        v+=(texture(moments,uv+d*3.230769231)+texture(moments,uv-d*3.230769231))*.070270270;
        out_fragColor=v;
        return;
    }
    // Same Gaussian kernel, with exact nearest taps instead of float-linear
    // sampling, which is optional for 32-bit textures in WebGL.
    v+=(texture(moments,uv+d)+texture(moments,uv-d))*.194594595;
    v+=(texture(moments,uv+d*2.0)+texture(moments,uv-d*2.0))*.121621622;
    v+=(texture(moments,uv+d*3.0)+texture(moments,uv-d*3.0))*.054054054;
    v+=(texture(moments,uv+d*4.0)+texture(moments,uv-d*4.0))*.016216216;
    out_fragColor=v;
}
