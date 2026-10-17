-- Two independent gesture roles, fixed at contact start even across the center.
local M={}
function M.new() return {contacts={},forward=false} end
function M.reset(s) s.contacts={};s.forward=false;s.look_id=nil end
function M.apply(s,touches,width,height)
    local seen={};local dx,dy=0,0
    for _,t in ipairs(touches) do
        seen[t.id]=true
        if t.released then
            s.contacts[t.id]=nil
            if s.look_id==t.id then s.look_id=nil end
        else
            local x=(t.screen_x or t.x)/width
            local y=(t.screen_y or t.y)/height
            local c=s.contacts[t.id]
            if not c then
                c={left=x<.5,x=x,y=y};s.contacts[t.id]=c
                if not c.left and not s.look_id then s.look_id=t.id end
            elseif s.look_id==t.id then dx=dx+x-c.x;dy=dy+y-c.y end
            c.x=x;c.y=y
        end
    end
    s.forward=false
    for id,c in pairs(s.contacts) do
        if not seen[id] then
            s.contacts[id]=nil
            if s.look_id==id then s.look_id=nil end
        elseif c.left then s.forward=true
        elseif not s.look_id then s.look_id=id end
    end
    return dx,dy
end
return M
