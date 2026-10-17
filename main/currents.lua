-- Shared, continuous world-space water velocity (metres/second). Standing
-- waves reverse gently; nothing follows the camera or changes an actor mesh.
local M={}
function M.sample(x,y,z,t)
    local depth=math.max(0,50-y)
    local a=.20+.07*math.exp(-depth*.025)
    return a*(math.sin(t*.72+z*.035)+.35*math.sin(t*.31+x*.045)),
        .055*math.sin(t*.63+x*.035+z*.022),
        a*(.75*math.sin(t*.58+x*.032)+.25*math.sin(t*.27-z*.04))
end
return M
