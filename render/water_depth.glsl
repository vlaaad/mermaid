// Relative to the existing shallow ruins. Red daylight fades fastest;
// blue fill survives farther down without turning the deep basin pitch black.
vec3 waterDaylight(float y) {
    return exp(-max(4.0-y,0.0)*vec3(.026,.018,.012));
}
vec3 waterHazeLight(float eyeY,float rayY) {
    return waterDaylight(eyeY+max(rayY,0.0)*20.0);
}
