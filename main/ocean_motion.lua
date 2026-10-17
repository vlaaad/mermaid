-- Sparse skeletal swimmers. Paths are in world coordinates, independent of
-- the camera; a small current response keeps the animals in the shared water.
local routes=require 'main.ocean_routes'
local currents=require 'main.currents'
local M={}
local function sample(r,t)
    local a=r.phase+(t-3)*r.rate;local c=r.center
    local x=c.x+r.rx*math.cos(a);local y=c.y+r.height*math.sin(a*2);local z=c.z+r.rz*math.sin(a)
    local vx=-r.rx*r.rate*math.sin(a);local vy=2*r.height*r.rate*math.cos(a*2);local vz=r.rz*r.rate*math.cos(a)
    local q=vmath.quat_rotation_y(math.atan2(-vx,-vz))*vmath.quat_rotation_x(math.atan2(vy,math.sqrt(vx*vx+vz*vz)))*vmath.quat_rotation_z(.055*math.sin(a))
    return vmath.vector3(x,y,z),q
end
function M.new(rays)
    local animals={}
    for i,r in ipairs(rays) do
        animals[#animals+1]={id=r.id,url=r.url,asset='ray',center=r.anchor-vmath.vector3(0,0,5),rx=i==1 and 13 or 10,rz=5,height=.35,phase=math.pi/2,rate=.055-i*.005,period=3.6,seed=i*.31,scale=r.scale.x}
    end
    for i,r in ipairs(routes) do
        animals[#animals+1]={id=r.id,url=r.id..'#model',asset='whale',center=vmath.vector3(r.center[1],r.center[2],r.center[3]),rx=r.radius[1],rz=r.radius[2],height=r.height,phase=r.phase,rate=r.rate,period=5.8,seed=i*.29,scale=r.scale}
    end
    return animals
end
function M.reset(animals,t)
    for _,a in ipairs(animals) do
        a.drift=vmath.vector3();a.p,a.q=sample(a,t);a.pose_tick=nil
        go.set_position(a.p,a.id);go.set_rotation(a.q,a.id)
        model.play_anim(a.url,'swim',go.PLAYBACK_LOOP_FORWARD,{playback_rate=0})
        go.set(a.url,'cursor',(t/a.period+a.seed)%1)
    end
end
function M.update(animals,dt,t,player,frozen)
    for i,a in ipairs(animals) do
        if not frozen then
            local x,y,z=currents.sample(a.p.x,a.p.y,a.p.z,t)
            a.drift=a.drift+(vmath.vector3(x,y,z)*(a.asset=='whale' and .06 or .25)-a.drift*.12)*dt
        end
        a.p,a.q=sample(a,t);a.p=a.p+a.drift
        go.set_position(a.p,a.id);go.set_rotation(a.q,a.id)
        local near=vmath.length_sqr(a.p-player)<2500
        local tick=math.floor(t*10+i*.4)
        if frozen or near or tick~=a.pose_tick then
            go.set(a.url,'cursor',(t/a.period+a.seed)%1);a.pose_tick=tick
        end
    end
end
function M.state(animals)
    local result={}
    for _,a in ipairs(animals) do
        result[#result+1]={id=a.id,asset=a.asset,x=a.p.x,y=a.p.y,z=a.p.z,scale=a.scale,cursor=go.get(a.url,'cursor')}
    end
    return result
end
return M
