#version 140
in highp vec3 var_world;
out highp vec4 out_fragColor;
void main() {

    // Shift both exponential warps into [-1,1]. Defold clears color through
    // uint8 values, so an empty texel must be expressible as (1,1,0,0).
    highp float z=gl_FragCoord.z;
    highp vec2 d=vec2(exp(32.0*(z-1.0)),-exp(-32.0*z));
    highp vec2 dx=dFdx(d),dy=dFdy(d);
    highp vec2 variance=.25*(dx*dx+dy*dy);
    out_fragColor=vec4(d.x,d.x*d.x+variance.x,d.y,d.y*d.y+variance.y);
}
