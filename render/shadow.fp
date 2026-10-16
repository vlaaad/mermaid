#version 140
in highp vec3 var_world;
out vec4 out_fragColor;
void main(){if(var_world.y< -4.4)discard;out_fragColor=vec4(1.0);}
