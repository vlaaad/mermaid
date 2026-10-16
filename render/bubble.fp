#version 140
in mediump vec2 var_uv;
in highp float var_depth;
out vec4 out_fragColor;
void main() {
    vec2 p=vec2(var_uv.x,1.0-var_uv.y)*2.0-1.0;
    float r=length(p),aa=max(fwidth(r),.015);
    float edge=1.0-smoothstep(1.0-aa,1.0,r);
    float rim=smoothstep(.57,.96,r)*.36;
    float glint=exp(-dot(p-vec2(-.32,.38),p-vec2(-.32,.38))*95.0)*.7;
    float alpha=(rim+glint)*edge*exp(-max(var_depth-3.0,0.0)*.022);
    out_fragColor=vec4(vec3(.94,.98,1.0)*alpha,alpha);
}
