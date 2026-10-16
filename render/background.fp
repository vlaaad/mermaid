#version 140
in mediump vec2 var_uv;
out vec4 out_fragColor;
uniform fs_uniforms {
 highp mat4 inverse_view_projection;
 highp vec4 camera_pos;
 mediump vec4 fog_settings;
 mediump vec4 visual_debug;
};
void main(){
 if(visual_debug.x>4.5){out_fragColor=vec4(0.0,0.0,0.0,1.0);return;}
 vec2 uv=vec2(var_uv.x,1.0-var_uv.y);
 vec4 farPoint=inverse_view_projection*vec4(uv*2.0-1.0,1.0,1.0);
 vec3 ray=normalize(farPoint.xyz/farPoint.w-camera_pos.xyz);
 vec3 sun=normalize(vec3(.35,.90,-.24));
 vec3 fog=mix(vec3(0.061000,0.485000,0.875000),fog_settings.rgb,clamp(ray.y*.9+.42,0.0,1.0));
 fog+=vec3(.012,.035,.04)*pow(max(dot(ray,sun),0.0),5.0);
 out_fragColor=vec4(fog,1.0);
}
