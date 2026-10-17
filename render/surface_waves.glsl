// Only the water surface deforms here. Actor poses belong to their skeletons.
// Height and its exact XZ gradient travel together to the optical shader.
vec3 surfaceWave(vec2 p,float t) {
    vec3 phase=vec3(dot(p,vec2(.25,.10))-t*1.625,
                    dot(p,vec2(-.19,.37))-t*2.020+1.7,
                    dot(p,vec2(.43,.25))-t*2.209+3.1);
    vec3 heights=vec3(.48,.24,.13)*sin(phase);
    vec3 derivatives=vec3(.48,.24,.13)*cos(phase);
    return vec3(heights.x+heights.y+heights.z,
                dot(derivatives,vec3(.25,-.19,.43)),
                dot(derivatives,vec3(.10,.37,.25)));
}
