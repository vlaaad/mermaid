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
    mediump vec4 visual_debug;
    mediump vec4 fog_settings;
    highp vec4 camera_pos;
    highp mat4 light_matrix;
};
// One-variable fitting pass: caustic contribution only.
const float CAUSTIC_GAIN=.90;
const float STONE_CAUSTIC_RESPONSE=.35;
const vec3 ROCK_AMBIENT_GAIN=vec3(1.8,1.4,1.15);
const vec3 ROCK_SUN_GAIN=vec3(.05,.20,.25);
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
    float radius=clamp(1.5+max(q.z-blocker,0.0)*150.0*.12*1024.0/100.0,1.5,7.0);
    float sum=0.0;
    for(int i=0;i<4;i++) {
        float angle=float(i)*2.399963;
        vec2 offset=vec2(cos(angle),sin(angle))*sqrt((float(i)+.5)/4.0)*radius/1024.0;
        vec2 tap=(floor((q.xy+offset)*1024.0)+.5)/1024.0;
        float receiver=q.z+dot(slope,tap-q.xy)-bias;
        sum+=step(receiver,texture(sun_depth,tap).r);
    }
    return sum/4.0;
}

vec3 surfaceColor(float t) {
    vec3 shaded;
    // Underside of a distant wave field: sloping wave facets refract skylight.
    // Layered directional waves replace the obvious tiled caustic ceiling.
    vec2 p=var_world.xz;
    vec2 uv1=p*.005+vec2(t*.0015,-t*.001);
    vec2 uv2=mat2(.80,-.60,.60,.80)*p*.013+vec2(-t*.001,t*.0018);
    float h1=texture(caustics,uv1).b;
    float h2=texture(caustics,uv2).b;
    vec2 warp=vec2(h1,h2)-.5;
    vec2 fineUV=mat2(.94,-.342,.342,.94)*p*.070+warp*.31+vec2(t*.001,-t*.002);
    float facets=texture(caustics,fineUV).b;
    float ridge=texture(caustics,p*.0425+warp*.23+vec2(-t*.002,0)).r;
    float clarity=1.0-smoothstep(90.0,180.0,var_depth);
    facets=mix(.5,facets,clarity*.10);
    ridge*=clarity*.70;
    vec2 e=vec2(1.0/256.0,0.0);
    vec2 slope=vec2(texture(caustics,fineUV+e.xy).b-texture(caustics,fineUV-e.xy).b,
                    texture(caustics,fineUV+e.yx).b-texture(caustics,fineUV-e.yx).b)*1.7;
    vec3 waterNormal=normalize(vec3(slope.x,-1.0,slope.y));
    vec3 view=normalize(camera_pos.xyz-var_world);
    float facing=max(dot(waterNormal,view),0.0);
    float fresnel=.02+.98*pow(1.0-facing,5.0);
    vec3 transmitted=mix(vec3(.065,.55,.89),vec3(.25,.76,.95),smoothstep(.17,.81,facets));
    transmitted+=vec3(.04,.07,.08)*ridge;
    vec3 reflected=mix(vec3(.025,.40,.77),vec3(.12,.65,.95),facets);
    shaded=mix(transmitted,reflected,fresnel*.6);
    float glow=exp(-dot((p-vec2(48.0,-80.0))/vec2(55.0,60.0),(p-vec2(48.0,-80.0))/vec2(55.0,60.0)));
    shaded+=vec3(.2976,.4176,.3036)*glow;
    return shaded*vec3(.50,.77,.98);
}
vec3 fogged(vec3 shaded,float density,bool surface) {
    // Suspended sediment makes water near the basin floor more turbid.
    // This follows world height in every camera view, including orbit/swimming.
    density*=1.0+(1.0-smoothstep(-3.0,7.0,var_world.y))*.90;
    float blend=1.0-exp(-max(var_depth-3.0,0.0)*density);
    vec3 ray=normalize(var_world-camera_pos.xyz);
    vec3 sun=normalize(vec3(.35,.90,-.24));
    vec3 fog=mix(vec3(0.061000,0.485000,0.875000),fog_settings.rgb,clamp(ray.y*.9+.42,0.0,1.0));
    fog+=vec3(.012,.035,.04)*pow(max(dot(ray,sun),0.0),5.0);
    if(surface)blend=max(blend,smoothstep(165.0,300.0,var_depth));
    return mix(shaded,fog,blend);
}
void main() {
    if(visual_debug.x>4.5) {
        float architecture=(params.x<.5 && var_color.a<.4)?1.0:0.0;
        out_fragColor=vec4(vec3(architecture),1.0);
        return;
    }
    // Surface pixels do not need stone textures, caustic receivers or eight PCF taps.
    if(params.x>3.5 && params.x<4.5) {
        out_fragColor=vec4(fogged(surfaceColor(time_data.x),fog_settings.w*.22,true),1.0);
        return;
    }
    vec3 n=normalize(var_normal);
    vec3 geometric=n;
    if(!gl_FrontFacing && params.x>.5 && params.x<1.5)n=-n;
    vec3 sun=normalize(vec3(.35,.90,-.24));
    float diffuse=max(dot(n,sun),0.0);
    // Bias a thin fin toward the light on either side to avoid self-shadow acne.
    if(params.x>2.5 && params.x<3.5 && var_color.a>.37 && var_color.a<.62 && dot(geometric,sun)<0.0)geometric=-geometric;
    float shadow=visibility(var_world,geometric,diffuse);
    float t=time_data.x;
    // Refraction projects a larger pattern onto receiving surfaces, absent in shade.
    vec2 uv=(var_world.xz+var_world.y*vec2(-.389,.267))*.035;
    uv+=vec2(sin(var_world.z*.16+t*.35),cos(var_world.x*.13+t*.29))*.022;
    float c1=texture(caustics,uv+vec2(t*.006,t*.004)).r;
    float c2=texture(caustics,uv*1.31+vec2(-t*.004,t*.007)).r;
    float pattern=pow(c1,.65)*.70+pow(c2,.65)*.45;
    float sky=n.y*.5+.5;
    vec3 ambient=mix(vec3(.13,.25,.34),vec3(.40,.59,.68),sky);
    // Broad bounced sand light gives undersides a cool green fill.
    ambient+=vec3(.10,.19,.14)*(1.0-sky)*exp(-max(var_world.y,0.0)*.085);
    bool roughStone=params.x<.5 && var_color.a>.4 && var_color.b>var_color.r && var_color.r<.4 && var_color.b<.55;
    vec3 base=var_color.rgb;
    // Blue-grey limestone reflectance; coral, sand and actors stay unchanged.
    if(params.x<.5 && base.b>base.r && base.r<.4 && base.b<.55)base*=var_color.a>.4?vec3(.49,.39,.69):vec3(.68,.57,.86);
    // The column shafts use a cooler limestone palette than the surrounding rock.
    if(params.x<.5 && var_color.a<.15)base*=vec3(.50,1.08,1.45);
    // Sand reflectance only; keep the projected caustic contribution fixed.
    if(params.x>7.5)base*=vec3(.675,1.035,1.215);
    if(params.x<.5 && base.b>base.r && base.r<.4) {
        vec3 weights=pow(abs(n),vec3(5.0));
        weights/=max(dot(weights,vec3(1.0)),.00001);
        vec2 detail=texture(stone_detail,var_world.zy*.28).rg*weights.x;
        detail+=texture(stone_detail,var_world.xz*.28).rg*weights.y;
        detail+=texture(stone_detail,var_world.xy*.28).rg*weights.z;
        base*=.78+detail.y*.43;
        vec3 dp1=dFdx(var_world),dp2=dFdy(var_world);
        vec3 r1=cross(dp2,n),r2=cross(n,dp1);
        float determinant=dot(dp1,r1);
        if(abs(determinant)>.0000001)n=normalize(n-(dFdx(detail.x)*r1+dFdy(detail.x)*r2)*.006/determinant);
    }
    diffuse=max(dot(n,sun),0.0);
    float weather=sin(var_world.x*1.3+sin(var_world.z*1.1))*sin(var_world.y*2.4+var_world.z*.8);
    vec3 materialAmbient=ambient;
    vec3 sunlight=vec3(1.38,1.26,.77);
    if(roughStone) { materialAmbient*=ROCK_AMBIENT_GAIN;sunlight*=ROCK_SUN_GAIN; }
    vec3 shaded=base*(materialAmbient+sunlight*diffuse*shadow)*(.95+weather*.05);
    float causticResponse=params.x>7.5?.56:STONE_CAUSTIC_RESPONSE;
    shaded+=vec3(.78,.88,.53)*pattern*(max(n.y,0.0)*.65+diffuse*.35)*shadow*CAUSTIC_GAIN*causticResponse;
    if(params.x<.5 && (base.r>.45 || base.b>.55))shaded+=base*.18;
    if(params.x>0.5 && params.x<1.5) {
        float transmission=pow(max(dot(-n,sun),0.0),2.0);
        float leafLight=.30+.70*abs(dot(n,sun));
        shaded=base*(vec3(.30,.46,.23)+vec3(1.85,1.65,.60)*leafLight*shadow);
        shaded+=base*vec3(.42,.58,.22)*transmission*shadow*.7;
        shaded*=vec3(.95,.75,1.05); // Cool green fronds retain warm sunlit edges.
    }
    if(params.x>1.5 && params.x<2.5) {
        shaded=base*(vec3(.60,.65,.48)+vec3(.75,.79,.53)*diffuse*shadow);
    }
    if(params.x>2.5 && params.x<3.5) {
        vec3 view=normalize(camera_pos.xyz-var_world);
        float rim=pow(1.0-max(dot(n,view),0.0),3.0);
        vec3 fill=vec3(.62,.61,.55),direct=vec3(.86,.86,.74);
        if(var_color.a>.12 && var_color.a<.62) {fill=vec3(.38,.61,.69);direct=vec3(.70,.86,.87);}
        if(var_color.a>.37 && var_color.a<.62) {fill=vec3(.48,.55,.55);direct=vec3(.65,.70,.55);}
        shaded=base*(fill+direct*diffuse*shadow);
        shaded+=vec3(.32,.48,.35)*rim*.40*shadow;
        vec3 halfVector=normalize(view+sun);
        float spec=pow(max(dot(n,halfVector),0.0),24.0)*shadow;
        shaded+=vec3(.35,.42,.32)*spec*.18;
        shaded+=vec3(.18,.37,.32)*pattern*.13*shadow;
        if(var_color.a>.37 && var_color.a<.62) {
            float phase=var_uv.x*44.0;
            float distanceToVein=abs(fract(phase+.5)-.5);
            float width=max(fwidth(phase),.025);
            float vein=(1.0-smoothstep(.025,.025+width,distanceToVein))*smoothstep(.02,.12,var_uv.y);
            shaded=mix(shaded,shaded*vec3(.65,.95,1.20)+vec3(.025,.07,.10),vein*.65);
            shaded+=base*vec3(.10,.08,.03);
            shaded*=vec3(1.99,1.86,1.30); // Pale yellow-green transmitted light through the fin.
        }
        if(var_color.a>.62 && var_color.a<.87) {
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
        if(var_color.a>.12 && var_color.a<.37) {
            vec2 scaleUV=vec2(var_uv.x*26.0,var_uv.y*34.0);
            scaleUV.x+=mod(floor(scaleUV.y),2.0)*.5;
            vec2 cell=fract(scaleUV)-.5;
            float scales=smoothstep(.47,.37,length(cell*vec2(1.0,1.6)));
            shaded*=.92+scales*.12;
            shaded+=vec3(.05,.14,.10)*pow(max(dot(n,halfVector),0.0),45.0);
        }
    }
    if(params.x>5.5 && params.x<6.5) {
        shaded=base*(vec3(.55,.66,.69)+vec3(.65,.71,.59)*diffuse*shadow);
    }
    float density=fog_settings.w;
    if(params.x>2.5 && params.x<3.5)density*=.4;
    shaded=fogged(shaded,density,false);
    out_fragColor=vec4(shaded,1.0);
}
