#version 140
in mediump vec2 var_uv;
out vec4 out_fragColor;
uniform highp sampler2D scene_depth;
uniform highp sampler2D sun_depth;
uniform mediump sampler2D solar_flux;
uniform fs_uniforms {
    highp mat4 inverse_view_projection;
    highp mat4 light_matrix;
    highp vec4 camera_pos;
    mediump vec4 visual_debug;
};
highp vec3 worldAt(highp vec2 uv,highp float depth) {
    highp vec4 p=inverse_view_projection*vec4(uv*2.0-1.0,depth*2.0-1.0,1.0);
    return p.xyz/p.w;
}
highp float linearDepth(highp float d){return .15*400.0/(400.0-d*(400.0-.15));}
float sunVisible(highp vec3 p) {
    highp vec3 q=(light_matrix*vec4(p,1.0)).xyz*.5+.5;
    if(q.x<.002 || q.y<.002 || q.x>.998 || q.y>.998 || q.z<0.0 || q.z>1.0)return 1.0;
    // Filter visibility, never raw shadow depth. The soft depth transition also
    // resolves partial occlusion along a water interval instead of switching it.
    vec2 pixel=q.xy*2048.0-.5,base=floor(pixel),f=fract(pixel);
    vec2 uv=(base+.5)/2048.0;
    vec4 depths=vec4(texture(sun_depth,uv).r,texture(sun_depth,uv+vec2(1,0)/2048.0).r,
                     texture(sun_depth,uv+vec2(0,1)/2048.0).r,texture(sun_depth,uv+vec2(1,1)/2048.0).r);
    vec4 v=smoothstep(vec4(q.z-.0018),vec4(q.z+.0002),depths);
    return mix(mix(v.x,v.y,f.x),mix(v.z,v.w,f.x),f.y);
}
void main() {
    highp vec2 uv=vec2(var_uv.x,1.0-var_uv.y);
    highp float depth=texture(scene_depth,uv).r,z=linearDepth(depth);
    highp vec3 hit=worldAt(uv,depth),delta=hit-camera_pos.xyz;
    highp float travel=length(delta);
    highp vec3 dir=delta/max(travel,.0001),sun=normalize(vec3(.35,.90,-.24));
    float end=min(travel,100.0),start=0.0;
    if(abs(dir.y)>.0001) {
        float a=(-100.0-camera_pos.y)/dir.y,b=(50.0-camera_pos.y)/dir.y;
        start=max(start,min(a,b));end=min(end,max(a,b));
    }
    // Integrate a uniform participating medium. Ruins occlude the sun; there
    // are no authored beam sprites, aperture cylinders or moving noise clouds.
    // Anchor interval boundaries to world planes to avoid a sample lattice
    // following the player. The dominant ray axis keeps all intervals bounded.
    vec3 ad=abs(dir),axis=vec3(0,0,1);
    if(ad.x>=ad.y && ad.x>=ad.z)axis=vec3(1,0,0);
    else if(ad.y>=ad.z)axis=vec3(0,1,0);
    float origin=dot(camera_pos.xyz,axis),rate=dot(dir,axis);
    const float spacing=1.75;
    float plane=floor(origin/spacing)*spacing;
    if(rate>0.0)plane+=spacing;
    float first=(plane-origin)/rate,stepLength=spacing/abs(rate);
    // Prefilter each interval's footprint on the aperture, so a camera move
    // cannot jump across a narrow beam between adjacent integration samples.
    // Four quadrature taps filter along the integration interval rather than
    // blurring a whole interval equally in every direction across the shafts.
    float apertureFootprint=length(dir.xz-dir.y*sun.xz/sun.y)*stepLength;
    float intervalLod=log2(max(apertureFootprint,1.0));
    // One footprint per view ray; avoid a logarithm for every water sample.
    float spread=max(intervalLod,log2(max(max(50.0-camera_pos.y,0.0)*.028,1.0)));
    vec2 apertureOrigin=(camera_pos.xz+(50.0-camera_pos.y)*sun.xz/sun.y)/64.0;
    vec2 apertureRate=(dir.xz-dir.y*sun.xz/sun.y)/64.0;
    // Beer-Lambert extinction along the view and the incoming sunlight path.
    // Integrate transmittance exactly within each interval (Hillaire 2015).
    const float extinction=.0165;
    float combined=extinction-.008*dir.y/sun.y;
    float transmission=exp(-combined*start),scatter=0.0,lo=start;
    for(int i=0;i<64;i++) {
        float hi=min(end,first+float(i)*stepLength);
        if(hi>lo) {
            float nextTransmission=exp(-combined*hi);
            highp vec3 p=camera_pos.xyz+dir*((lo+hi)*.5);
            // Project onto the water plane along the sun direction. Irradiance
            // stays fixed along each light path, never in camera/screen space.
            vec2 aperture=apertureOrigin+apertureRate*((lo+hi)*.5);
            vec2 tap=apertureRate*(hi-lo)*.125;
            float energy=textureLod(solar_flux,aperture-tap*3.0,spread).r;
            energy+=textureLod(solar_flux,aperture-tap,spread).r;
            energy+=textureLod(solar_flux,aperture+tap,spread).r;
            energy+=textureLod(solar_flux,aperture+tap*3.0,spread).r;
            float flux=.04+energy*1.8;
            scatter+=sunVisible(p)*flux*(transmission-nextTransmission)*exp(-max(4.0-p.y,0.0)*.018);
            transmission=nextTransmission;
            lo=hi;
        }
        if(lo>=end)break;
    }
    float mu=dot(dir,sun),g=.50;
    float phase=(1.0-g*g)/pow(1.0+g*g-2.0*g*mu,1.5);
    float solarTransmission=exp(-max(50.0-camera_pos.y,0.0)*.008/sun.y);
    vec3 color=vec3(.90,.98,1.0)*scatter*(extinction/combined)*solarTransmission*phase*.14;
    if(visual_debug.x>.5 && visual_debug.x<1.5)color=vec3(z/70.0);
    if(visual_debug.x>1.5 && visual_debug.x<2.5)color=vec3(scatter*.5);
    if(visual_debug.x>2.5 && visual_debug.x<3.5)color=vec3(sunVisible(hit));
    if(visual_debug.x>3.5 && visual_debug.x<4.5)color=fract(hit*.04);
    out_fragColor=vec4(color,z);
}
