#version 140
in mediump vec2 var_uv;
out vec4 out_fragColor;
uniform mediump sampler2D scene_texture;
uniform highp sampler2D scene_depth;
uniform mediump sampler2D water_texture;
uniform fs_uniforms { mediump vec4 screen_size; mediump vec4 visual_debug; };
float linearDepth(float d){return .15*180.0/(180.0-d*(180.0-.15));}
void main() {
    vec2 uv=vec2(var_uv.x,1.0-var_uv.y);
    vec3 color=texture(scene_texture,uv).rgb;
    float z=linearDepth(texture(scene_depth,uv).r);
    float contact=0.0;
    for(int i=0;i<8;i++) {
        float a=float(i)*2.399963;
        vec2 offset=vec2(cos(a),sin(a))*(4.0+float(i)*1.9)/screen_size.xy;
        float neighbor=linearDepth(texture(scene_depth,uv+offset).r);
        float gap=z-neighbor;
        contact+=smoothstep(.08,.55,gap)*(1.0-smoothstep(1.3,3.5,gap));
    }
    color*=1.0-contact*.05;
    // Depth-aware upsampling smooths the water without smearing across the character.
    vec2 pixel=uv*screen_size.zw-.5;
    vec2 base=floor(pixel),f=fract(pixel);
    vec3 water=vec3(0.0);
    float total=0.0;
    for(int x=0;x<2;x++)for(int y=0;y<2;y++) {
        vec2 tap=vec2(float(x),float(y));
        vec4 v=texture(water_texture,(base+tap+.5)/screen_size.zw);
        vec2 b=mix(vec2(1.0)-f,f,tap);
        float weight=b.x*b.y/(1.0+abs(v.a*180.0-z)*3.0);
        water+=v.rgb*weight;
        total+=weight;
    }
    water/=max(total,.00001);
    color+=water;
    color=color/(vec3(1.0)+color*.15)*1.08;
    if(visual_debug.x>.5)color=water;
    out_fragColor=vec4(color,1.0);
}
