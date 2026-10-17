// World-space illumination. Red daylight fades fastest below the shallow ruins.
vec3 waterDaylight(float y) {
    return exp(-max(4.0-y,0.0)*vec3(.026,.018,.012));
}
// Integrate available scattered light along the sightline. Reuse interval
// endpoints instead of evaluating two complete exponentials on each side of
// the shallow-water plateau. Bright-water intervals need no RGB exponential.
highp vec3 waterScattering(highp float eyeY,highp float hitY,highp float travel,highp float density) {
    highp float tau=max(travel-3.0,0.0)*density;
    highp float transmission=exp(-tau);
    if(min(eyeY,hitY)>=4.0)return vec3(1.0-transmission);
    const highp vec3 falloff=vec3(.055,.044,.032);
    highp vec3 coefficient=vec3(tau)-falloff*(hitY-eyeY);
    highp vec3 first,last;
    highp float above=0.0,span=1.0;
    if(eyeY>=4.0) {
        highp float split=(4.0-eyeY)/(hitY-eyeY);
        highp float splitTransmission=exp(-tau*split);
        above=1.0-splitTransmission;span=1.0-split;
        first=vec3(splitTransmission);
        last=transmission*exp(-max(4.0-hitY,0.0)*falloff);
    } else {
        first=exp(-(4.0-eyeY)*falloff);
        if(hitY>4.0) {
            highp float split=(4.0-eyeY)/(hitY-eyeY);
            highp float splitTransmission=exp(-tau*split);
            above=splitTransmission-transmission;span=split;
            last=vec3(splitTransmission);
        } else last=transmission*exp(-(4.0-hitY)*falloff);
    }
    // The limit at zero extinction/light gradient is finite. Avoid the
    // cancellation and 0/0 that would otherwise band upward-looking water.
    highp vec3 a=coefficient*span;
    highp vec3 stable=step(vec3(.002),abs(a));
    highp vec3 denominator=mix(vec3(.002),coefficient,stable);
    highp vec3 integral=mix(tau*span*first*(vec3(1.0)-a*.5),tau*(first-last)/denominator,stable);
    return vec3(above)+integral;
}
