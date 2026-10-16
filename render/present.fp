#version 140
in mediump vec2 var_uv;
out vec4 out_fragColor;
uniform mediump sampler2D scene_texture;
uniform fs_uniforms {
    highp vec4 screen_size;
    mediump vec4 antialias;
};
float luma(vec3 color){return dot(color,vec3(.299,.587,.114));}
vec3 edgeAA(highp vec2 uv,vec3 center) {
    highp vec2 pixel=1.0/screen_size.xy;
    float nw=luma(texture(scene_texture,uv+vec2(-1,-1)*pixel).rgb);
    float ne=luma(texture(scene_texture,uv+vec2(1,-1)*pixel).rgb);
    float sw=luma(texture(scene_texture,uv+vec2(-1,1)*pixel).rgb);
    float se=luma(texture(scene_texture,uv+vec2(1,1)*pixel).rgb);
    float middle=luma(center);
    float low=min(middle,min(min(nw,ne),min(sw,se)));
    float high=max(middle,max(max(nw,ne),max(sw,se)));
    // Keep low-contrast water and flat surfaces untouched.
    if(high-low<max(.025,high*.125))return center;
    highp vec2 direction=vec2(sw+se-nw-ne,nw+sw-ne-se);
    float reduction=max((nw+ne+sw+se)*.03125,.0078125);
    direction=clamp(direction/(min(abs(direction.x),abs(direction.y))+reduction),vec2(-8),vec2(8))*pixel;
    vec3 narrow=.5*(texture(scene_texture,uv-direction/6.0).rgb+texture(scene_texture,uv+direction/6.0).rgb);
    vec3 wide=narrow*.5+.25*(texture(scene_texture,uv-direction*.5).rgb+texture(scene_texture,uv+direction*.5).rgb);
    float wideLuma=luma(wide);
    return wideLuma<low || wideLuma>high?narrow:wide;
}
void main(){
    highp vec2 uv=vec2(var_uv.x,1.0-var_uv.y);
    vec3 color=texture(scene_texture,uv).rgb;
    if(antialias.x>.5)color=edgeAA(uv,color);
    out_fragColor=vec4(color,1.0);
}
