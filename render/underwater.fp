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
float visibility(vec3 p,vec3 normal,float ndl) {
    if(abs(light_matrix[3].w)<.0001)return 1.0;
    vec4 light=light_matrix*vec4(p+normal*.025,1.0);
    vec3 q=light.xyz/light.w*.5+.5;
    vec3 dx=dFdx(q),dy=dFdy(q);
    float det=dx.x*dy.y-dx.y*dy.x;
    vec2 slope=vec2(dy.y*dx.z-dx.y*dy.z,dx.x*dy.z-dy.x*dx.z)/((abs(det)>.0000000001)?det:1.0);
    slope=clamp(slope,vec2(-1.0),vec2(1.0));
    if(q.x<.002 || q.y<.002 || q.x>.998 || q.y>.998 || q.z>1.0 || q.z<0.0)return 1.0;
    float bias=.00015+.00012*(1.0-ndl);
    float blocker=texture(sun_depth,q.xy).r;
    float radius=clamp(1.5+max(q.z-blocker,0.0)*150.0*.12*2048.0/100.0,1.5,7.0);
    float sum=0.0;
    for(int i=0;i<8;i++) {
        float angle=float(i)*2.399963;
        vec2 offset=vec2(cos(angle),sin(angle))*sqrt((float(i)+.5)/8.0)*radius/2048.0;
        vec2 tap=(floor((q.xy+offset)*2048.0)+.5)/2048.0;
        float receiver=q.z+dot(slope,tap-q.xy)-bias;
        sum+=step(receiver,texture(sun_depth,tap).r);
    }
    return sum/8.0;
}

void main() {
    vec3 n=normalize(var_normal);
    vec3 geometric=n;
    if(!gl_FrontFacing && params.x>.5 && params.x<1.5)n=-n;
    vec3 sun=normalize(vec3(.35,.90,-.24));
    float diffuse=max(dot(n,sun),0.0);
    float shadow=visibility(var_world,geometric,diffuse);
    float t=time_data.x;
    // Refraction projects a larger pattern onto receiving surfaces, absent in shade.
    vec2 uv=(var_world.xz+var_world.y*vec2(-.389,.267))*.065;
    uv+=vec2(sin(var_world.z*.16+t*.35),cos(var_world.x*.13+t*.29))*.022;
    float c1=texture(caustics,uv+vec2(t*.006,t*.004)).r;
    float c2=texture(caustics,uv*1.31+vec2(-t*.004,t*.007)).r;
    float pattern=min(c1,c2)*1.9+max(c1,c2)*.25;
    float sky=n.y*.5+.5;
    vec3 ambient=mix(vec3(.13,.25,.34),vec3(.40,.59,.68),sky);
    // Broad bounced sand light gives undersides a cool green fill.
    ambient+=vec3(.10,.19,.14)*(1.0-sky)*exp(-max(var_world.y,0.0)*.085);
    vec3 base=var_color.rgb;
    if(params.x<.5 && base.b>base.r && base.r<.4) {
        vec3 weights=pow(abs(n),vec3(5.0));
        weights/=max(dot(weights,vec3(1.0)),.00001);
        vec2 detail=texture(caustics,var_world.zy*.23).gb*weights.x;
        detail+=texture(caustics,var_world.xz*.23).gb*weights.y;
        detail+=texture(caustics,var_world.xy*.23).gb*weights.z;
        base*=.87+detail.y*.24;
        vec3 dp1=dFdx(var_world),dp2=dFdy(var_world);
        vec3 r1=cross(dp2,n),r2=cross(n,dp1);
        float determinant=dot(dp1,r1);
        if(abs(determinant)>.0000001)n=normalize(n-(dFdx(detail.x)*r1+dFdy(detail.x)*r2)*.006/determinant);
    }
    diffuse=max(dot(n,sun),0.0);
    float weather=sin(var_world.x*1.3+sin(var_world.z*1.1))*sin(var_world.y*2.4+var_world.z*.8);
    vec3 shaded=base*(ambient+vec3(1.03,.98,.78)*diffuse*shadow)*(.95+weather*.05);
    shaded+=vec3(.23,.46,.45)*pattern*max(n.y,0.0)*shadow*.35;
    if(params.x<.5 && (base.r>.45 || base.b>.55))shaded+=base*.18;
    if(params.x>0.5 && params.x<1.5) {
        float transmission=pow(max(dot(-n,sun),0.0),2.0);
        shaded+=base*vec3(.42,.58,.22)*transmission*shadow*.7;
    }
    if(params.x>2.5 && params.x<3.5) {
        vec3 view=normalize(camera_pos.xyz-var_world);
        float rim=pow(1.0-max(dot(n,view),0.0),3.0);
        shaded=base*(vec3(.60,.57,.48)+vec3(.86,.82,.63)*diffuse*shadow);
        shaded+=vec3(.32,.48,.35)*rim*.40*shadow;
        vec3 halfVector=normalize(view+sun);
        float spec=pow(max(dot(n,halfVector),0.0),24.0)*shadow;
        shaded+=vec3(.35,.42,.32)*spec*.18;
        shaded+=vec3(.18,.37,.32)*pattern*.13*shadow;
        if(base.r>.55 && base.g>.38 && base.b<base.g*.60) {
            float grooves=.96+.04*sin(var_uv.x*90.0);
            shaded*=grooves*(.92+var_uv.y*.08);
            vec3 dp1=dFdx(var_world),dp2=dFdy(var_world);
            vec2 duv1=dFdx(var_uv),duv2=dFdy(var_uv);
            vec3 tangent=dp2*duv1.x-dp1*duv2.x;
            float len=length(tangent);
            if(len>.000001) {
                tangent/=len;
                float anisotropic=pow(sqrt(max(0.0,1.0-pow(dot(tangent,halfVector),2.0))),44.0);
                shaded+=vec3(.22,.19,.12)*anisotropic*shadow;
            }
        }
        if(var_local.y<.12 && base.g>base.r*2.0) {
            vec2 scaleUV=vec2(var_uv.x*26.0,var_uv.y*44.0);
            scaleUV.x+=mod(floor(scaleUV.y),2.0)*.5;
            vec2 cell=fract(scaleUV)-.5;
            float scales=smoothstep(.47,.37,length(cell*vec2(1.0,1.6)));
            shaded*=.92+scales*.12;
            shaded+=vec3(.05,.14,.10)*pow(max(dot(n,halfVector),0.0),45.0);
        }
    }
    if(params.x>3.5 && params.x<4.5) {
        // Underside of a distant wave field: sloping wave facets refract skylight.
        // Layered directional waves replace the obvious tiled caustic ceiling.
        vec2 p=var_world.xz;
        vec2 uv1=p*.019+vec2(t*.0015,-t*.001);
        vec2 uv2=p*.037+vec2(-t*.001,t*.0018);
        float h1=texture(caustics,uv1).b;
        float h2=texture(caustics,uv2).b;
        vec2 warp=vec2(h1,h2)-.5;
        vec2 fineUV=p*.10+warp*.15+vec2(t*.001,-t*.002);
        float facets=texture(caustics,fineUV).b;
        float ridge=texture(caustics,p*.065+warp*.13+vec2(-t*.002,0)).r;
        vec2 e=vec2(1.0/256.0,0.0);
        vec2 slope=vec2(texture(caustics,fineUV+e.xy).b-texture(caustics,fineUV-e.xy).b,
                        texture(caustics,fineUV+e.yx).b-texture(caustics,fineUV-e.yx).b)*1.7;
        vec3 waterNormal=normalize(vec3(slope.x,-1.0,slope.y));
        vec3 view=normalize(camera_pos.xyz-var_world);
        float facing=max(dot(waterNormal,view),0.0);
        float fresnel=.02+.98*pow(1.0-facing,5.0);
        vec3 transmitted=mix(vec3(.065,.48,.75),vec3(.36,.77,.91),smoothstep(.17,.81,facets));
        transmitted+=vec3(.08,.16,.17)*ridge;
        vec3 reflected=mix(vec3(.025,.32,.55),vec3(.12,.53,.74),facets);
        shaded=mix(transmitted,reflected,fresnel*.6);
        float glow=exp(-dot((p-vec2(22.0,-44.0))/vec2(32.0,36.0),(p-vec2(22.0,-44.0))/vec2(32.0,36.0)));
        shaded+=vec3(.10,.19,.20)*glow;

    }
    float fogDensity=fog_settings.w;
    if(params.x>2.5 && params.x<3.5)fogDensity*=.4;
    float distanceFog=1.0-exp(-max(var_depth-3.0,0.0)*fogDensity);
    vec3 waterRay=normalize(var_world-camera_pos.xyz);
    vec3 fog=mix(vec3(.025,.33,.54),fog_settings.rgb,clamp(waterRay.y*.9+.42,0.0,1.0));
    fog+=vec3(.012,.035,.04)*pow(max(dot(waterRay,sun),0.0),5.0);
    if(params.x>3.5 && params.x<4.5)distanceFog=max(distanceFog,smoothstep(70.0,135.0,var_depth));
    shaded=mix(shaded,fog,distanceFog);
    out_fragColor=vec4(shaded,1.0);
}
