#version 140
in highp vec3 var_world;
out highp vec4 out_fragColor;
void main() {
    if(var_world.y< -4.4)discard;
    highp float w=40.0*(gl_FragCoord.z-.5);
    highp vec2 d=vec2(exp(w),-exp(-w));
    highp vec2 dx=dFdx(d),dy=dFdy(d);
    highp vec2 variance=.25*(dx*dx+dy*dy);
    out_fragColor=vec4(d.x,d.x*d.x+variance.x,d.y,d.y*d.y+variance.y);
}
