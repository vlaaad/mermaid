#version 140
in mediump vec2 var_uv;
out vec4 out_fragColor;
uniform highp sampler2D scene_depth;
uniform highp sampler2D sun_depth;
uniform fs_uniforms {
    highp mat4 inverse_view_projection;
    highp mat4 light_matrix;
    highp vec4 camera_pos;
    mediump vec4 time_data;
    mediump vec4 screen_size;
    mediump vec4 visual_debug;
};
vec3 worldAt(vec2 uv,float depth) {
    vec4 p=inverse_view_projection*vec4(uv*2.0-1.0,depth*2.0-1.0,1.0);
    return p.xyz/p.w;
}
float linearDepth(float d){return .15*400.0/(400.0-d*(400.0-.15));}
float sunVisible(vec3 p) {
    vec4 l=light_matrix*vec4(p,1.0);
    vec3 q=l.xyz/l.w*.5+.5;
    if(q.x<0.0 || q.y<0.0 || q.x>1.0 || q.y>1.0)return 1.0;
    return step(q.z-.0014,texture(sun_depth,q.xy).r);
}
void main() {
    // glTF imports V flipped. All render-target lookups use the restored UV.
    vec2 uv=vec2(var_uv.x,1.0-var_uv.y);
    vec3 color=vec3(0.0);
    float depth=texture(scene_depth,uv).r;
    vec3 hit=worldAt(uv,depth);
    vec3 delta=hit-camera_pos.xyz;
    float travel=length(delta);
    vec3 dir=delta/max(travel,.0001);
    float z=linearDepth(depth);
    // Integrate actual world-space water up to the opaque surface. No ray cards.
    // Surface ripples modulate sunlight along parallel refracted light paths.
    float limit=min(travel,80.0);
    float stride=limit/32.0;
    float jitter=fract(dot(floor(gl_FragCoord.xy),vec2(.75487766,.56984029)));
    float scatter=0.0;
    for(int i=0;i<32;i++) {
        float d=(float(i)+jitter)*stride;
        vec3 p=camera_pos.xyz+dir*d;
        vec2 surface=p.xz+(50.0-p.y)*vec2(.389,-.267);
        vec2 wave=vec2(sin(surface.y*.35+time_data.x*.11),cos(surface.x*.29-time_data.x*.09))*.6;
        vec2 s=surface+wave;
        vec2 a=(s-vec2(18.1,-39.2))/vec2(1.5,8.0);
        vec2 b=(s-vec2(31.1,-57.2))/vec2(2.2,10.0);
        vec2 c=(s-vec2(6.1,-31.2))/vec2(1.25,7.0);
        vec2 e=(s-vec2(20.1,-20.2))/vec2(1.8,7.5);
        float aperture=exp(-dot(a,a))+exp(-dot(b,b))*.8+exp(-dot(c,c))*.7+exp(-dot(e,e))*.6;
        float filaments=.72+.20*sin(s.x*5.2+s.y*.65+time_data.x*.13)+.08*sin(s.x*11.0+s.y*.35);
        aperture*=filaments;
        float water=smoothstep(-6.0,-3.5,p.y)*(1.0-smoothstep(49.0,51.0,p.y));
        scatter+=(.025+aperture)*sunVisible(p)*water*exp(-d*.027)*stride;
    }
    float forward=.75+pow(max(dot(dir,normalize(vec3(.35,.90,-.24))),0.0),3.0)*1.7;
    color+=vec3(.48,.68,.76)*scatter*.085*forward;
    if(visual_debug.x>.5 && visual_debug.x<1.5)color=vec3(z/70.0);
    if(visual_debug.x>1.5 && visual_debug.x<2.5)color=vec3(scatter*.12);
    if(visual_debug.x>2.5 && visual_debug.x<3.5)color=vec3(sunVisible(hit));
    if(visual_debug.x>3.5 && visual_debug.x<4.5)color=fract(hit*.04);
    out_fragColor=vec4(color,clamp(z/180.0,0.0,1.0));
}
