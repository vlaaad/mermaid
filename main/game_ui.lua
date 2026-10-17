-- Invisible in-game profiler hit region. There is no rendered node or GUI.
local M={}
function M.layout(w,h)
    local size=math.max(72,math.min(w,h)*.10)
    return {size=size,margin=0,profile_x=w-size*.5,y=h-size*.5}
end
function M.hit(x,y,w,h)
    local l=M.layout(w,h)
    if y<h-l.margin-l.size or y>h-l.margin then return nil end
    if math.abs(x-l.profile_x)<=l.size*.5 then return 'profiler' end
end
function M.filter_touches(contacts,touches,w,h)
    local filtered,events,seen={},{},{}
    for _,t in ipairs(touches) do
        seen[t.id]=true
        if contacts[t.id]==nil and not t.released then
            local role=M.hit(t.screen_x or t.x,t.screen_y or t.y,w,h)
            contacts[t.id]=role or false
            if role then events[#events+1]=role end
        end
        if not contacts[t.id] then filtered[#filtered+1]=t end
        if t.released then contacts[t.id]=nil end
    end
    for id in pairs(contacts) do if not seen[id] then contacts[id]=nil end end
    return filtered,events
end
function M.activate(state,role)
    if role=='profiler' then
        state.profiling=not state.profiling
        state.profile_last=nil;state.profile_fps=nil;state.profile_elapsed=0;state.profile_frames=0
        profiler.enable_ui(state.profiling)
        if state.profiling then
            profiler.set_ui_view_mode(profiler.VIEW_MODE_MINIMIZED)
        end
    end
end
return M
