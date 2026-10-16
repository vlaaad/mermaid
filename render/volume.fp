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
    float stride=limit/24.0;
    // Midpoint integration is spatially continuous. A static per-pixel hash at
    // quarter resolution imprints a 4px checker/noise pattern on the ceiling.
    float jitter=.5;
    float scatter=0.0;
    for(int i=0;i<24;i++) {
        float d=(float(i)+jitter)*stride;
        vec3 p=camera_pos.xyz+dir*d;
        float below=50.0-p.y;
        vec2 surface=p.xz+below*vec2(.389,-.267);
        // Refraction by different wave slopes spreads the shafts slightly. Each
        // remains a world-space volume, occluded by the same sun shadow map.
        vec2 slope=vec2(sin(surface.y*.12+time_data.x*.17),cos(surface.x*.14-time_data.x*.13));
        vec2 s=surface+slope*(.30+below*.035);
        float bands=.5+.5*sin(s.x*.73+s.y*.19+sin(s.y*.21)*1.5);
        float broken=.5+.5*sin(s.y*.34-s.x*.15+time_data.x*.08);
        float b2=bands*bands,b4=b2*b2,b8=b4*b4;
        float narrow=b8*b8*(.25+.75*broken*broken*broken);
        float w=.5+.5*sin(s.x*.31+s.y*.11+1.7);
        float w2=w*w,w4=w2*w2;
        float wide=w4*w4*w2;
        vec2 patch=(s-vec2(18,-38))/vec2(65,85);
        float aperture=(narrow*.95+wide*.22)*exp(-dot(patch,patch));
        float water=smoothstep(-6.0,-3.5,p.y)*(1.0-smoothstep(49.0,51.0,p.y));
        scatter+=(.025+aperture)*sunVisible(p)*water*exp(-d*.027)*stride;
    }
    float forward=.75+pow(max(dot(dir,normalize(vec3(.35,.90,-.24))),0.0),3.0)*1.7;
    color+=vec3(.54,.65,.68)*scatter*.055*forward;
    if(visual_debug.x>.5 && visual_debug.x<1.5)color=vec3(z/70.0);
    if(visual_debug.x>1.5 && visual_debug.x<2.5)color=vec3(scatter*.12);
    if(visual_debug.x>2.5 && visual_debug.x<3.5)color=vec3(sunVisible(hit));
    if(visual_debug.x>3.5 && visual_debug.x<4.5)color=fract(hit*.04);
    out_fragColor=vec4(color,clamp(z/180.0,0.0,1.0));
}
