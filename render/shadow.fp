#version 140
in highp vec3 var_world;
out vec4 out_fragColor;
void main(){
    // Broken column bases and cliff foundations extend below the seabed.
    // They cannot cast sunlight through the ground from their buried back faces.
    if(var_world.y<-.4)discard;
    out_fragColor=vec4(1.0);
}
