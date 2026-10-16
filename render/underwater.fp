#version 140
in highp vec3 var_world;
in mediump vec3 var_normal;
in mediump vec4 var_color;
in mediump vec2 var_uv;
in highp float var_depth;
in mediump vec3 var_local;
out vec4 out_fragColor;
uniform mediump sampler2D caustics;
uniform highp sampler2D sun_depth;
uniform fs_uniforms {
    mediump vec4 time_data;
    mediump vec4 params;
    mediump vec4 fog_settings;
    highp vec4 camera_pos;
    highp mat4 light_matrix;
};
float visibility(vec3 p, float ndl) {
    vec4 light=light_matrix*vec4(p,1.0);
    vec3 q=light.xyz/light.w*.5+.5;
    if(q.x<.002 || q.y<.002 || q.x>.998 || q.y>.998 || q.z>1.0)return 1.0;
    float bias=.0028+.0025*(1.0-ndl);
    float sum=0.0;
    for(int x=0;x<3;x++)for(int y=0;y<3;y++) {
        vec2 offset=(vec2(float(x),float(y))-1.0)*1.4/1024.0;
        sum+=step(q.z-bias,texture(sun_depth,q.xy+offset).r);
    }
    return sum/9.0;
}
void main() {
    vec3 n=normalize(var_normal);
    if(!gl_FrontFacing && params.x>.5 && params.x<1.5)n=-n;
    vec3 sun=normalize(vec3(.35,.90,-.24));
    float diffuse=max(dot(n,sun),0.0);
    float shadow=visibility(var_world,diffuse);
    float t=time_data.x;
    // Refraction projects a larger pattern onto receiving surfaces, absent in shade.
    vec2 uv=(var_world.xz+var_world.y*vec2(-.389,.267))*.045;
    uv+=vec2(sin(var_world.z*.16+t*.35),cos(var_world.x*.13+t*.29))*.022;
    float c1=texture(caustics,uv+vec2(t*.006,t*.004)).r;
    float c2=texture(caustics,uv*1.31+vec2(-t*.004,t*.007)).r;
    float pattern=min(c1,c2)*1.9+max(c1,c2)*.25;
    float sky=n.y*.5+.5;
    vec3 ambient=mix(vec3(.12,.28,.38),vec3(.38,.63,.77),sky);
    // Broad bounced sand light gives undersides a cool green fill.
    ambient+=vec3(.09,.17,.13)*(1.0-sky)*exp(-max(var_world.y,0.0)*.085);
    vec3 base=var_color.rgb;
    if(params.x<.5 && base.b>base.r && base.r<.4) {
        // World-space mineral mottling avoids repeating a texture on every instance.
        float grain=sin(var_world.x*4.2+sin(var_world.z*2.7))*sin(var_world.y*5.8+var_world.z*3.1);
        float mineral=sin(var_world.x*.85+var_world.y*2.7+sin(var_world.z*.76)*2.0);
        base*=.90+mineral*.08+grain*.035;
    }
    float weather=sin(var_world.x*1.3+sin(var_world.z*1.1))*sin(var_world.y*2.4+var_world.z*.8);
    vec3 shaded=base*(ambient+vec3(1.03,.98,.78)*diffuse*shadow)*(.95+weather*.05);
    shaded+=vec3(.23,.46,.45)*pattern*max(n.y,0.0)*shadow*.48;
    if(params.x<.5 && (base.r>.45 || base.b>.55))shaded+=base*.18;
    if(params.x>0.5 && params.x<1.5) {
        float transmission=pow(max(dot(-n,sun),0.0),2.0);
        shaded+=base*vec3(.42,.58,.22)*transmission*shadow*.7;
    }
    if(params.x>2.5 && params.x<3.5) {
        vec3 view=normalize(camera_pos.xyz-var_world);
        float rim=pow(1.0-max(dot(n,view),0.0),3.0);
        shaded=base*(vec3(.39,.51,.56)+vec3(.94,.87,.66)*diffuse*shadow);
        shaded+=vec3(.32,.48,.35)*rim*.40*shadow;
        vec3 halfVector=normalize(view+sun);
        float spec=pow(max(dot(n,halfVector),0.0),24.0)*shadow;
        shaded+=vec3(.35,.42,.32)*spec*.18;
        shaded+=vec3(.18,.37,.32)*pattern*.13*shadow;
        if(var_local.y<.12 && base.g>base.r*2.0) {
            float scales=sin(var_local.y*65.0+sin(var_local.x*65.0)*.7)*.5+.5;
            shaded*=.94+scales*.12;
        }
    }
    if(params.x>3.5 && params.x<4.5) {
        float ripple=sin(var_world.x*.7+t*.5+sin(var_world.z*.6))*sin(var_world.z*.43-t*.3)*.5+.5;
        shaded=mix(vec3(.07,.51,.78),vec3(.28,.80,.94),clamp(pattern*.55+ripple*.28,0.0,1.0));
    }
    float distanceFog=1.0-exp(-max(var_depth-3.0,0.0)*fog_settings.w);
    vec3 fog=mix(vec3(.025,.30,.49),fog_settings.rgb,clamp(var_world.y/26.0,0.0,1.0));
    shaded=mix(shaded,fog,distanceFog);
    out_fragColor=vec4(shaded,1.0);
}
