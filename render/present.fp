#version 140
in mediump vec2 var_uv;
out vec4 out_fragColor;
uniform mediump sampler2D scene_texture;
void main(){out_fragColor=texture(scene_texture,vec2(var_uv.x,1.0-var_uv.y));}
