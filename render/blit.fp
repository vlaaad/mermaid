#version 140
in mediump vec2 var_uv;
out vec4 out_fragColor;
uniform mediump sampler2D scene_texture;
uniform highp sampler2D scene_depth;
uniform highp sampler2D water_texture;
uniform fs_uniforms { mediump vec4 screen_size; mediump vec4 visual_debug; };
float linearDepth(float d){return .15*400.0/(400.0-d*(400.0-.15));}
void main() {
    vec2 uv=vec2(var_uv.x,1.0-var_uv.y);
    vec3 color=texture(scene_texture,uv).rgb;
    if(visual_debug.x>4.5){out_fragColor=vec4(color,1.0);return;}
    float z=linearDepth(texture(scene_depth,uv).r);
    // Depth-aware upsampling smooths the water without smearing across the character.
    vec2 pixel=uv*screen_size.zw-.5;
    vec2 base=floor(pixel),f=fract(pixel);
    vec3 water=vec3(0.0);
    float total=0.0;
    // Grazing surfaces can change depth by many meters across a 4px footprint.
    // Follow that slope, but cap tolerance relative to the foreground depth so
    // a silhouette never admits distant background scattering.
    float footprint=4.0*length(vec2(dFdx(z),dFdy(z)));
    float tolerance=max(clamp(z*.035,.25,10.0),min(footprint,z*.12));
    for(int x=0;x<2;x++)for(int y=0;y<2;y++) {
        vec2 tap=vec2(float(x),float(y));
        vec4 v=texture(water_texture,(base+tap+.5)/screen_size.zw);
        vec2 b=mix(vec2(1.0)-f,f,tap);
        float agreement=1.0-smoothstep(tolerance,tolerance*2.0,abs(v.a-z));
        float weight=b.x*b.y*agreement;
        water+=v.rgb*weight;
        total+=weight;
    }
    water*=smoothstep(0.0,.35,total)/max(total,.00001);
    color+=water;
    color=color/(vec3(1.0)+color*.15)*1.08;
    if(visual_debug.x>.5)color=water;
    out_fragColor=vec4(color,1.0);
}
