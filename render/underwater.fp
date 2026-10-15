#version 140
in highp vec3 var_world;
in mediump vec3 var_normal;
in mediump vec4 var_color;
in mediump vec2 var_uv;
in highp float var_depth;
in mediump vec3 var_local;
out vec4 out_fragColor;
uniform mediump sampler2D caustics;
uniform mediump sampler2D stone_detail;
uniform highp sampler2D sun_depth;
uniform fs_uniforms {
    mediump vec4 time_data;
    mediump vec4 params;
    mediump vec4 fog_settings;
    highp vec4 camera_pos;
    highp mat4 light_matrix;
    mediump vec4 art_ambient_top;
    mediump vec4 art_ambient_bottom;
    mediump vec4 art_sun;
    mediump vec4 art_fog_bottom;
};
float visibility(vec3 p,vec3 normal,float ndl) {
    if(abs(light_matrix[3].w)<.0001)return 1.0; // Editor resource preview has no sun map.
    // Offset in world units, then correct receiver-plane depth across the PCF taps.
    vec4 light=light_matrix*vec4(p+normal*.025,1.0);
    vec3 q=light.xyz/light.w*.5+.5;
    vec3 dx=dFdx(q),dy=dFdy(q);
    float det=dx.x*dy.y-dx.y*dy.x;
    vec2 slope=vec2(dy.y*dx.z-dx.y*dy.z,dx.x*dy.z-dy.x*dx.z)/((abs(det)>.0000000001)?det:1.0);
    slope=clamp(slope,vec2(-1.0),vec2(1.0));
    if(q.x<.002 || q.y<.002 || q.x>.998 || q.y>.998 || q.z>1.0 || q.z<0.0)return 1.0;
    float bias=.00013+.00010*(1.0-ndl);
    float blocker=texture(sun_depth,q.xy).r;
    float radius=clamp(1.5+max(q.z-blocker,0.0)*150.0*.12*2048.0/100.0,1.5,9.0);
    float sum=0.0;
    for(int i=0;i<12;i++) {
        float angle=float(i)*2.399963;
        vec2 offset=vec2(cos(angle),sin(angle))*sqrt((float(i)+.5)/12.0)*radius/2048.0;
        vec2 tap=(floor((q.xy+offset)*2048.0)+.5)/2048.0;
        float receiver=q.z+dot(slope,tap-q.xy)-bias;
        sum+=step(receiver,texture(sun_depth,tap).r);
    }
    return sum/12.0;
}
void main() {
    vec3 n=normalize(var_normal);
    vec3 geometric=n;
    vec3 base=var_color.rgb;
    if(params.x<.5 && base.b>base.r && base.r<.4) {
        vec3 weights=pow(abs(n),vec3(6.0));
        weights/=max(dot(weights,vec3(1.0)),.00001);
        vec3 detail=texture(stone_detail,var_world.zy*.30).rgb*weights.x;
        detail+=texture(stone_detail,var_world.xz*.30).rgb*weights.y;
        detail+=texture(stone_detail,var_world.xy*.30).rgb*weights.z;
        float height=dot(detail,vec3(.299,.587,.114));
        base*=.83+height*.30;
        vec3 dp1=dFdx(var_world),dp2=dFdy(var_world);
        vec3 r1=cross(dp2,n),r2=cross(n,dp1);
        float determinant=dot(dp1,r1);
        if(abs(determinant)>.0000001)n=normalize(n-(dFdx(height)*r1+dFdy(height)*r2)*.006/determinant);
    }
    if(!gl_FrontFacing && params.x>.5 && params.x<1.5)n=-n;
    vec3 sun=normalize(vec3(.35,.90,-.24));
    float diffuse=max(dot(n,sun),0.0);
    float shadow=visibility(var_world,geometric,diffuse);
    float t=time_data.x;
    // Refraction projects a larger pattern onto receiving surfaces, absent in shade.
    vec2 uv=(var_world.xz+var_world.y*vec2(-.389,.267))*.045;
    uv+=vec2(sin(var_world.z*.16+t*.35),cos(var_world.x*.13+t*.29))*.022;
    float c1=texture(caustics,uv+vec2(t*.006,t*.004)).r;
    float c2=texture(caustics,uv*1.31+vec2(-t*.004,t*.007)).r;
    float pattern=min(c1,c2)*.8+max(c1,c2)*.8;
    float sky=n.y*.5+.5;
    vec3 ambient=mix(art_ambient_bottom.rgb,art_ambient_top.rgb,sky);
    // Broad bounced sand light gives undersides a cool green fill.
    ambient+=vec3(.09,.17,.13)*(1.0-sky)*exp(-max(var_world.y,0.0)*.085);
    if(params.x<.5 && base.b>base.r && base.r<.4) {
        // World-space mineral mottling avoids repeating a texture on every instance.
        float grain=sin(var_world.x*4.2+sin(var_world.z*2.7))*sin(var_world.y*5.8+var_world.z*3.1);
        float mineral=sin(var_world.x*.85+var_world.y*2.7+sin(var_world.z*.76)*2.0);
        base*=.90+mineral*.08+grain*.035;
    }
    float weather=sin(var_world.x*1.3+sin(var_world.z*1.1))*sin(var_world.y*2.4+var_world.z*.8);
    vec3 shaded=base*(ambient+art_sun.rgb*diffuse*shadow)*(.95+weather*.05);
    shaded+=vec3(.23,.46,.45)*pattern*max(n.y,0.0)*shadow*art_ambient_top.w;
    if(params.x<.5 && (base.r>.45 || base.b>.55))shaded+=base*.28;
    if(params.x>0.5 && params.x<1.5) {
        float transmission=pow(max(dot(-n,sun),0.0),2.0);
        shaded+=base*vec3(.42,.58,.22)*transmission*shadow*.7;
    }
    if(params.x>1.5 && params.x<2.5)shaded=base*(vec3(.55,.65,.55)+vec3(.75,.75,.55)*diffuse*shadow);
    if(params.x>2.5 && params.x<3.5) {
        vec3 view=normalize(camera_pos.xyz-var_world);
        float rim=pow(1.0-max(dot(n,view),0.0),3.0);
        shaded=base*(vec3(.65,.58,.48)+vec3(.94,.87,.66)*diffuse*shadow);
        shaded+=vec3(.32,.48,.35)*rim*.40*shadow;
        vec3 halfVector=normalize(view+sun);
        float spec=pow(max(dot(n,halfVector),0.0),24.0)*shadow;
        shaded+=vec3(.35,.42,.32)*spec*.18;
        shaded+=vec3(.18,.37,.32)*pattern*.13*shadow;
        if(var_local.y<.12 && base.g>base.r*2.0) {
            vec2 center=vec2(clamp(var_local.y*.14,-.25,0.0),.05-var_local.y*.72);
            float around=atan(var_local.x-center.x,var_local.z-center.y)*8.0;
            float rows=-var_local.y*18.0;
            float cell=fract(around+mod(floor(rows),2.0)*.5)-.5;
            float arc=sqrt(max(0.0,1.0-cell*cell*4.0))*.34;
            float edge=1.0-smoothstep(.025,.075,abs(fract(rows)-arc-.25));
            shaded*=.89+fract(rows)*.11;
            shaded+=vec3(.03,.13,.10)*edge;
        }
    }
    if(params.x>3.5 && params.x<4.5) {
        vec2 water=var_world.xz*.80;
        water+=vec2(sin(water.y*.8+t*.12),cos(water.x*.7-t*.1))*.8;
        float ripple=sin(water.x*2.1+sin(water.y*1.7))*sin(water.y*2.6+cos(water.x*1.1));
        ripple+=.45*sin(water.x*4.7-water.y*3.0+t*.15);
        float patches=smoothstep(-.35,.75,ripple);
        shaded=mix(vec3(.055,.55,.80),vec3(.18,.75,.87),patches)+vec3(.04,.06,.05)*pattern*.25;
    }
    float distanceFog=1.0-exp(-max(var_depth-3.0,0.0)*fog_settings.w);
    vec3 fog=mix(art_fog_bottom.rgb,fog_settings.rgb,clamp(var_world.y/48.0,0.0,1.0));
    if(params.x>2.5 && params.x<3.5)distanceFog*=.35;
    if(params.x>3.5 && params.x<4.5) {
        // Surface detail stays legible overhead, then merges with the distant clear color.
        distanceFog=smoothstep(80.0,175.0,var_depth);
        fog=fog_settings.rgb;
    }
    shaded=mix(shaded,fog,distanceFog);
    out_fragColor=vec4(shaded,1.0);
}
