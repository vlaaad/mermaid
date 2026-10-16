#version 140
#include "/render/water_depth.glsl"
in highp vec3 var_world;
in highp float var_depth;
out vec4 out_fragColor;
uniform mediump sampler2D caustics;
uniform fs_uniforms {
    mediump vec4 time_data;
    mediump vec4 fog_settings;
    mediump vec4 visual_debug;
    highp vec4 camera_pos;
};
vec3 surfaceColor(float t) {
    // GPU Gems wave-normal layering, with the water-to-air dielectric boundary.
    // World coordinates and normals stay high precision in the grazing view.
    highp vec2 p=var_world.xz;
    highp vec2 a=texture(caustics,p*.085+vec2(t*.0038,-t*.0021)).rg*2.0-1.0;
    highp vec2 b=texture(caustics,mat2(.80,-.60,.60,.80)*p*.16+vec2(-t*.0033,t*.0036)).rg*2.0-1.0;
    b=mat2(.80,.60,-.60,.80)*b;
    highp vec2 slope=a*.85+b*.35;
    slope+=vec2(.075,.030)*cos(dot(p,vec2(.48,.19))-t*.62);
    slope+=vec2(-.025,.055)*cos(dot(p,vec2(-.24,.53))-t*.85);
    highp vec3 n=normalize(vec3(slope.x,-1.0,slope.y));
    highp vec3 incident=normalize(var_world-camera_pos.xyz);
    highp float cosI=clamp(dot(-incident,n),.0001,1.0);
    const float eta=1.333;
    highp float k=1.0-eta*eta*(1.0-cosI*cosI);
    highp float cosT=sqrt(max(k,0.0));
    // Unresolved small wave slopes soften the critical-angle transition.
    highp float opticalCos=sqrt(max(k,.01));
    highp float rs=(eta*cosI-opticalCos)/(eta*cosI+opticalCos+.00001);
    highp float rp=(cosI-eta*opticalCos)/(cosI+eta*opticalCos+.00001);
    highp float edge=max(.045,fwidth(k)*1.5);
    highp float fresnel=mix(1.0,(rs*rs+rp*rp)*.5,smoothstep(-edge,edge,k));
    highp vec3 transmitted=eta*incident+(eta*cosI-cosT)*n;
    highp vec3 reflected=reflect(incident,n);
    // At this depth, distant underwater reflections are dominated by blue
    // scattered light. No additional scene render or screen-space ray march.
    highp vec3 under=mix(vec3(.055,.43,.69),vec3(.075,.54,.80),clamp(reflected.y*.5+.5,0.0,1.0));
    highp vec3 underwaterSun=normalize(vec3(.35,.90,-.24));
    highp vec3 sun=vec3(underwaterSun.x*eta,sqrt(1.0-dot(underwaterSun.xz,underwaterSun.xz)*eta*eta),underwaterSun.z*eta);
    highp float mu=dot(transmitted,sun);
    highp float aa=max(fwidth(mu),.000004);
    highp float disc=smoothstep(.999985-aa,.999985+aa,mu);
    highp float aureole=exp((min(mu,1.0)-1.0)*95.0);
    highp vec3 sky=mix(vec3(.58,.80,.92),vec3(.22,.54,.87),sqrt(clamp(transmitted.y,0.0,1.0)));
    sky*=vec3(.68,1.02,1.12);
    float halo=exp((min(mu,1.0)-1.0)*28.0);
    sky=mix(sky,vec3(.94,.98,1.0),halo*.85);
    sky+=vec3(2.4,2.35,2.2)*aureole+vec3(5.0,4.9,4.6)*disc;
    return mix(sky,under,fresnel);
}
void main() {
    if(visual_debug.x>4.5) {out_fragColor=vec4(0,0,0,1);return;}
    vec3 color=surfaceColor(time_data.x);
    vec3 ray=normalize(var_world-camera_pos.xyz);
    vec3 fog=mix(vec3(.061,.485,.875),fog_settings.rgb,clamp(ray.y*.9+.42,0.0,1.0));
    float blend=1.0-exp(-max(var_depth-3.0,0.0)*fog_settings.w);
    blend=max(blend,smoothstep(165.0,300.0,var_depth));
    fog*=waterHazeLight(camera_pos.y,ray.y);
    out_fragColor=vec4(mix(color,fog,blend),1.0);
}
