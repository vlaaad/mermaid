-- Fixed-step schools, rooted spring rigs and a bounded recycled bubble pool.
-- Bone tracks are real glTF animations; the shaders only skin those poses.
local anchors=require 'main.living_world'
local currents=require 'main.currents'
local collision=require 'main.collision'
local obstacles=require 'main.obstacles'
local M={}
local pi=math.pi
local function clamp(x,a,b)return math.max(a,math.min(b,x))end
local function length(x,y,z)return math.sqrt(x*x+y*y+z*z)end
-- World cells stay within +/-256: a numeric key avoids thousands of temporary
-- strings per simulation step while remaining exact in Lua's number format.
local function cell_key(x,y,z)return x+y*1024+z*1048576 end
local function key(x,y,z,size)return cell_key(math.floor(x/size),math.floor(y/size),math.floor(z/size))end
local function quat(a)return vmath.quat(a[1],a[2],a[3],a[4])end
local function position(a)return vmath.vector3(a[1],a[2],a[3])end
local function pose(url,clip,cursor)
    model.play_anim(url,clip,go.PLAYBACK_LOOP_FORWARD,{playback_rate=0})
    go.set(url,'cursor',clamp(cursor,.00001,.99999))
end
local function grid_add(grid,x,y,z,size,value)
    local k=key(x,y,z,size);local cell=grid[k]
    if not cell then cell={};grid[k]=cell end
    cell[#cell+1]=value
end
local function nearby(grid,x,y,z,size,radius,visit)
    for ix=math.floor((x-radius)/size),math.floor((x+radius)/size) do
        for iy=math.floor((y-radius)/size),math.floor((y+radius)/size) do
            for iz=math.floor((z-radius)/size),math.floor((z+radius)/size) do
                local cell=grid[cell_key(ix,iy,iz)]
                if cell then for _,v in ipairs(cell) do visit(v) end end
            end
        end
    end
end
function M.new()
    local s={fish={},plants={},bubbles={},drifters={},stone={},groups={},vents={},step=0,accumulator=0,phase=0,clip='idle',wake=0,vent_timer=0,serial=0,contacts=0,emitted=0,wake_emitted=0,neighbors=0}
    for _,a in ipairs(anchors) do
        local f={id=a.id,url=a.id..'#model',anchor=position(a.p),rotation=quat(a.q),scale=vmath.vector3(a.s[1],a.s[2],a.s[3]),asset=a.asset}
        if a.asset:sub(1,4)=='fish' then
            local k=a.asset..':'..key(a.p[1],a.p[2],a.p[3],24)
            local g=s.groups[k]
            if not g then g={x=0,y=0,z=0,count=0,phase=#s.fish*.7};s.groups[k]=g end
            g.x=g.x+a.p[1];g.y=g.y+a.p[2];g.z=g.z+a.p[3];g.count=g.count+1
            local scale=math.max(a.s[1],a.s[2],a.s[3])
            f.group=g;f.seed=#s.fish*.83;f.index=#s.fish+1;f.radius=.12*scale+.06
            f.half_length=.40*scale;f.personal=f.half_length+.50
            s.fish[#s.fish+1]=f
        elseif a.asset=='ray' then
            s.drifters[#s.drifters+1]=f
        elseif a.asset=='particle' then
            s.bubbles[#s.bubbles+1]=f
        else
            f.axis=vmath.rotate(f.rotation,vmath.vector3(0,0,1))
            f.height=(a.asset=='kelp' and 5.7 or 6.7)*a.s[2]
            f.seed=#s.plants*.71;s.plants[#s.plants+1]=f
        end
    end
    for _,g in pairs(s.groups) do g.x=g.x/g.count;g.y=g.y/g.count;g.z=g.z/g.count end
    for _,f in ipairs(s.fish) do
        local g=f.group
        f.station=vmath.vector3(f.anchor.x-g.x,f.anchor.y-g.y,f.anchor.z-g.z)*.65
        local d=vmath.length(f.station);if d>4 then f.station=f.station*(4/d) end
    end
    -- Static broad phase is built once, including the full convex hull extent.
    for _,b in ipairs(obstacles) do
        for x=math.floor((b[1]-b[4]-2)/6),math.floor((b[1]+b[4]+2)/6) do
            for y=math.floor((b[2]-b[5]-2)/6),math.floor((b[2]+b[5]+2)/6) do
                for z=math.floor((b[3]-b[6]-2)/6),math.floor((b[3]+b[6]+2)/6) do
                    local k=cell_key(x,y,z);s.stone[k]=s.stone[k] or {};table.insert(s.stone[k],b)
                end
            end
        end
    end
    for _,p in ipairs({{-5,2},{8,-7},{-12,-16},{-20,43},{24,68},{-25,70}}) do
        local x,z=p[1],p[2];local y=collision.floor_height(x,z)
        -- Find the upper supporting face here, so vents never emit inside stone.
        local list=s.stone[key(x,y+2,z,6)] or {}
        for _,b in ipairs(list) do
            if math.abs(x-b[1])<b[4] and math.abs(z-b[3])<b[6] and b[2]+b[5]<y+8 then y=math.max(y,b[2]+b[5]) end
        end
        s.vents[#s.vents+1]=vmath.vector3(x,y+.15,z)
    end
    return s
end
local stone_resolve,separate_fish
function M.reset(s,t)
    s.accumulator=0;s.step=0;s.frozen_applied=false;s.phase=t/1.8;s.clip='idle';s.pose_speed=0;s.wake=0;s.vent_timer=0;s.serial=0;s.contacts=0;s.emitted=0;s.wake_emitted=0;s.neighbors=0
    pose('/player#model','idle',s.phase%1)
    for i,f in ipairs(s.fish) do
        f.pose_tick=nil
        f.x,f.y,f.z=stone_resolve(s,f.anchor.x,f.anchor.y,f.anchor.z,f.radius)
        f.x,f.y,f.z=stone_resolve(s,f.x,f.y,f.z,f.radius)
        local v=vmath.rotate(f.rotation,vmath.vector3(1,0,0));f.vx=v.x*.8;f.vy=v.y*.8;f.vz=v.z*.8
        f.old=vmath.vector3(f.x,f.y,f.z);f.target=f.old
        go.set_position(f.old,f.id);go.set_rotation(f.rotation,f.id)
        pose(f.url,'swim',(t/.7+f.seed)%1)
    end
    for _=1,4 do separate_fish(s) end
    for _,f in ipairs(s.fish) do
        f.old=vmath.vector3(f.x,f.y,f.z);f.target=f.old;go.set_position(f.old,f.id)
    end
    for _,r in ipairs(s.drifters) do r.p=vmath.vector3(r.anchor);go.set_position(r.p,r.id) end
    for _,p in ipairs(s.plants) do p.bend=0;p.velocity=0;p.pose_tick=nil;pose(p.url,'bend',.5) end
    for _,b in ipairs(s.bubbles) do b.age=100;b.lifetime=0;go.set_scale(.0001,b.id) end
end
-- Maximum separating plane is an exact inside test for the convex collision
-- volume. Project predicted fish positions outside with a small body clearance.
stone_resolve=function(s,x,y,z,r)
    local list=s.stone[key(x,y,z,6)] or {}
    for _=1,3 do
        local deepest,nx,ny,nz=0,0,0,0
        for _,b in ipairs(list) do
            if math.abs(x-b[1])<b[4]+r and math.abs(y-b[2])<b[5]+r and math.abs(z-b[3])<b[6]+r then
                local d,ax,ay,az=-1e9,0,0,0
                if b[7] then
                    for _,p in ipairs(b[7]) do
                        local v=x*p[1]+y*p[2]+z*p[3]-p[4]
                        if v>d then d=v;ax=p[1];ay=p[2];az=p[3] end
                    end
                else
                    local dx,dy,dz=math.abs(x-b[1])-b[4],math.abs(y-b[2])-b[5],math.abs(z-b[3])-b[6]
                    if dx>dy and dx>dz then d=dx;ax=x>b[1] and 1 or -1
                    elseif dy>dz then d=dy;ay=y>b[2] and 1 or -1
                    else d=dz;az=z>b[3] and 1 or -1 end
                end
                if r-d>deepest then deepest=r-d;nx=ax;ny=ay;nz=az end
            end
        end
        if deepest<=0 then break end
        x=x+nx*(deepest+.002);y=y+ny*(deepest+.002);z=z+nz*(deepest+.002)
    end
    return x,math.max(y,collision.floor_height(x,z)+r),z
end
-- A spatial broad phase enforces body clearance when steering alone is too
-- late. Symmetric corrections keep the school from collapsing into one point.
separate_fish=function(s)
    local grid={}
    for _,f in ipairs(s.fish) do
        f.push_x=0;f.push_y=0;f.push_z=0
        grid_add(grid,f.x,f.y,f.z,3,f)
    end
    for _,f in ipairs(s.fish) do
        nearby(grid,f.x,f.y,f.z,3,1.5,function(n)
            if n.index<=f.index then return end
            local dx,dy,dz=f.x-n.x,f.y-n.y,f.z-n.z
            local dd=dx*dx+dy*dy+dz*dz;local space=f.half_length+n.half_length+.30
            if dd<space*space then
                local d=math.sqrt(dd)
                if d<.00001 then dx=1;dy=0;dz=0;d=1;dd=0 end
                local push=(space-math.sqrt(dd))*.51/d
                dx=dx*push;dy=dy*push;dz=dz*push
                f.push_x=f.push_x+dx;f.push_y=f.push_y+dy;f.push_z=f.push_z+dz
                n.push_x=n.push_x-dx;n.push_y=n.push_y-dy;n.push_z=n.push_z-dz
            end
        end)
    end
    for _,f in ipairs(s.fish) do
        if f.push_x~=0 or f.push_y~=0 or f.push_z~=0 then
            f.x,f.y,f.z=stone_resolve(s,f.x+f.push_x,f.y+f.push_y,f.z+f.push_z,f.radius)
        end
        f.target=vmath.vector3(f.x,f.y,f.z)
    end
    return grid
end
local function schools(s,dt,t,player,body)
    local grid={};s.neighbors=0
    for _,f in ipairs(s.fish) do grid_add(grid,f.x,f.y,f.z,3,f) end
    -- Double buffer forces: neighbor velocities/positions belong to one time step.
    for _,f in ipairs(s.fish) do
        local sx,sy,sz,cx,cy,cz,ax,ay,az,count=0,0,0,0,0,0,0,0,0,0
        nearby(grid,f.x,f.y,f.z,3,2.6,function(n)
            if n==f then return end
            local dx,dy,dz=f.x-n.x,f.y-n.y,f.z-n.z;local dd=dx*dx+dy*dy+dz*dz
            if dd<6.76 and dd>.000001 then
                if n.asset==f.asset then cx=cx+n.x;cy=cy+n.y;cz=cz+n.z;ax=ax+n.vx;ay=ay+n.vy;az=az+n.vz;count=count+1 end
                local space=f.personal+n.personal
                if dd<space*space then local force=(space/math.sqrt(dd)-1)*8;sx=sx+dx*force;sy=sy+dy*force;sz=sz+dz*force end
            end
        end)
        s.neighbors=s.neighbors+count
        local g=f.group
        local tx=g.x+math.cos(t*.13+g.phase)*4+f.station.x;local ty=g.y+math.sin(t*.19+g.phase)*1.2+f.station.y;local tz=g.z+math.sin(t*.13+g.phase)*4+f.station.z
        local fx,fy,fz=(tx-f.x)*.16,(ty-f.y)*.20,(tz-f.z)*.16
        if count>0 then
            fx=fx+(cx/count-f.x)*.07+(ax/count-f.vx)*.8
            fy=fy+(cy/count-f.y)*.07+(ay/count-f.vy)*.8
            fz=fz+(cz/count-f.z)*.07+(az/count-f.vz)*.8
        end
        fx=fx+sx;fy=fy+sy;fz=fz+sz
        local dx,dy,dz=f.x-player.x,f.y-player.y,f.z-player.z;local distance=length(dx,dy,dz)
        if distance<3.2 and distance>.001 then local force=5*(1-distance/3.2)/distance;fx=fx+dx*force;fy=fy+dy*force;fz=fz+dz*force end
        local px,py,pz=f.x+f.vx*.8,f.y+f.vy*.8,f.z+f.vz*.8
        local ox,oy,oz=stone_resolve(s,px,py,pz,f.radius+.35)
        fx=fx+(ox-px)*5;fy=fy+(oy-py)*5;fz=fz+(oz-pz)*5
        f.nvx=f.vx+fx*dt;f.nvy=f.vy+fy*dt;f.nvz=f.vz+fz*dt
        local speed=length(f.nvx,f.nvy,f.nvz);local target=clamp(speed,.55,1.65)
        if speed>.00001 then f.nvx=f.nvx/speed*target;f.nvy=f.nvy/speed*target;f.nvz=f.nvz/speed*target end
    end
    for _,f in ipairs(s.fish) do
        f.vx=f.nvx;f.vy=f.nvy;f.vz=f.nvz
        local wx,wy,wz=currents.sample(f.x,f.y,f.z,t)
        f.old=vmath.vector3(f.x,f.y,f.z)
        f.x,f.y,f.z=stone_resolve(s,f.x+(f.vx+wx)*dt,f.y+(f.vy+wy)*dt,f.z+(f.vz+wz)*dt,f.radius)
    end
    s.fish_grid=separate_fish(s)
    -- Thrust can outrun soft steering. Project after crowd corrections so
    -- neither avoidance stage can push a fish back into the player.
    if body then
        for _,f in ipairs(s.fish) do
            if length(f.x-player.x,f.y-player.y,f.z-player.z)<4.5 then
                for _,b in ipairs(body) do
                    local dx,dy,dz=f.x-player.x-b[1],f.y-player.y-b[2],f.z-player.z-b[3]
                    local d=length(dx,dy,dz);local clearance=b[4]+f.radius
                    if d<clearance and d>.0001 then
                        local push=(clearance-d+.002)/d
                        f.x=f.x+dx*push;f.y=f.y+dy*push;f.z=f.z+dz*push
                    end
                end
                f.x,f.y,f.z=stone_resolve(s,f.x,f.y,f.z,f.radius)
                f.target=vmath.vector3(f.x,f.y,f.z)
            end
        end
    end
end
local function foliage(s,dt,t,player,body)
    for i,p in ipairs(s.plants) do
        local x,y,z=p.anchor.x,p.anchor.y+p.height*.5,p.anchor.z
        local wx,wy,wz=currents.sample(x,y,z,t)
        local force=(wx*p.axis.x+wz*p.axis.z)*1.4
        local touch=0
        if body then
            for _,b in ipairs(body) do
                local dx,dy,dz=x-player.x-b[1],y-player.y-b[2],z-player.z-b[3]
                -- Broad fronds flex when a body passes along their stem height.
                local distance=length(dx,dy*.45,dz);local radius=1+b[4]
                if distance<radius then touch=touch+(dx*p.axis.x+dz*p.axis.z)/math.max(.15,distance)*(1-distance/radius)*3 end
            end
        end
        if math.abs(touch)>.01 then s.contacts=s.contacts+1 end
        if s.fish_grid then
            nearby(s.fish_grid,x,y,z,3,1.3,function(f)
                local dx,dy,dz=x-f.x,y-f.y,z-f.z;local distance=length(dx,dy,dz)
                if distance<1.1 then force=force+(dx*p.axis.x+dz*p.axis.z)/math.max(.15,distance)*(1-distance/1.1)*.35 end
            end)
        end
        -- Damped angular spring, root locked; upper joints share
        -- the bend with increasing displacement through the weighted chain.
        local target=clamp(force+touch,-.95,.95)
        p.velocity=p.velocity+((target-p.bend)*12-p.velocity*6)*dt
        p.bend=clamp(p.bend+p.velocity*dt,-.95,.95)
        local distance=vmath.length_sqr(p.anchor-player)
        local tick=math.floor(t*5+i*.25)
        if distance<900 or tick~=p.pose_tick then go.set(p.url,'cursor',.5+p.bend*.48);p.pose_tick=tick end
    end
end
local function emit(s,p,t,wake)
    s.serial=s.serial+1;local b=s.bubbles[(s.serial-1)%#s.bubbles+1]
    local q=s.serial*2.39996
    b.p=p+vmath.vector3(math.cos(q)*.09,0,math.sin(q)*.09)
    b.age=0;b.lifetime=7+(s.serial%7)*.7;b.radius=(wake and .7 or 1.1)+s.serial%4*.25
    b.rise=.65+(s.serial%5)*.09;b.wake=wake
    s.emitted=s.emitted+1;if wake then s.wake_emitted=s.wake_emitted+1 end
end
local function bubbles(s,dt,t,player,rotation,speed)
    s.vent_timer=s.vent_timer+dt
    if s.vent_timer>.42 then
        s.vent_timer=s.vent_timer-.42
        local source=s.vents[(s.emitted%#s.vents)+1];emit(s,source,t,false)
    end
    if speed>.65 then
        s.wake=s.wake+dt*math.min(8,speed*1.25)
        while s.wake>=1 do
            s.wake=s.wake-1
            emit(s,player+vmath.rotate(rotation,vmath.vector3(.17,-.65,.65)),t,true)
        end
    else s.wake=0 end
    for _,b in ipairs(s.bubbles) do
        b.age=b.age+dt
        if b.age<b.lifetime then
            local wx,wy,wz=currents.sample(b.p.x,b.p.y,b.p.z,t)
            b.p=b.p+vmath.vector3(wx,wy+b.rise,wz)*dt
            if b.p.y>49.8 then b.age=b.lifetime end
        end
    end
end
function M.update(s,dt,t,player,rotation,speed,body,frozen)
    if frozen and s.frozen_applied then return end
    if not frozen then
        s.accumulator=math.min(s.accumulator+dt,.15)
        while s.accumulator>=.05 do
            s.step=s.step+1;s.accumulator=s.accumulator-.05
            local time=t-s.accumulator
            for _,r in ipairs(s.drifters) do
                local x,y,z=currents.sample(r.p.x,r.p.y,r.p.z,time)
                r.p=r.p+vmath.vector3(x,y,z)*.05+(r.anchor-r.p)*.002
            end
            if s.step%2==0 then schools(s,.1,time,player,body) end
            foliage(s,.05,time,player,body);bubbles(s,.05,time,player,rotation,speed)
        end
        s.phase=s.phase+dt*(.55+math.min(speed,8)*.17)/1.8
    end
    -- Cadence follows thrust smoothly; glide has a real, quieter joint action.
    s.pose_speed=s.pose_speed or speed
    s.pose_speed=frozen and speed or s.pose_speed+(speed-s.pose_speed)*(1-math.exp(-3*dt))
    local clip=s.pose_speed>2.4 and 'swim' or (s.pose_speed>.45 and 'glide' or 'idle')
    if clip~=s.clip then
        s.clip=clip;model.play_anim('/player#model',clip,go.PLAYBACK_LOOP_FORWARD,{playback_rate=0,blend_duration=frozen and 0 or .55})
    end
    go.set('/player#model','cursor',s.phase%1)
    local alpha=(s.accumulator+.05*(s.step%2))/.1
    for i,f in ipairs(s.fish) do
        go.set_position(vmath.lerp(alpha,f.old,f.target),f.id)
        local dx,dy,dz=f.x-player.x,f.y-player.y,f.z-player.z
        local near=dx*dx+dy*dy+dz*dz<400
        local tick=math.floor(t*10+i*.5)
        if frozen or near or tick~=f.pose_tick then
            local h=math.sqrt(f.vx*f.vx+f.vz*f.vz)
            local q=vmath.quat_rotation_y(math.atan2(-f.vz,f.vx))*vmath.quat_rotation_z(math.atan2(f.vy,h))
            go.set_rotation(q,f.id)
            go.set(f.url,'cursor',(t/.7+f.seed)%1);f.pose_tick=tick
        end
    end
    for _,r in ipairs(s.drifters) do go.set_position(r.p,r.id) end
    for _,b in ipairs(s.bubbles) do
        if b.age<b.lifetime then
            go.set_position(b.p,b.id)
            local envelope=clamp(b.age/.35,0,1)*clamp((b.lifetime-b.age)/1.2,0,1)
            go.set_scale(math.max(.0001,b.radius*envelope),b.id)
        else go.set_scale(.0001,b.id) end
    end
    s.frozen_applied=frozen
end
function M.state(s)
    local active=0;local max_bend=0;local travel=0;local penetration=0;local fish_samples={};local plant_samples={}
    for _,b in ipairs(s.bubbles) do if b.age<b.lifetime then active=active+1 end end
    for _,p in ipairs(s.plants) do max_bend=math.max(max_bend,math.abs(p.bend)) end
    for i,f in ipairs(s.fish) do
        travel=travel+vmath.length(vmath.vector3(f.x,f.y,f.z)-f.anchor)
        local x,y,z=stone_resolve(s,f.x,f.y,f.z,f.radius)
        penetration=math.max(penetration,length(x-f.x,y-f.y,z-f.z))
        if i<=7 then fish_samples[#fish_samples+1]={x=f.x,y=f.y,z=f.z} end
    end
    for i,p in ipairs(s.plants) do
        if vmath.length_sqr(p.anchor-vmath.vector3(-1,4.8,4))<400 then plant_samples[#plant_samples+1]={id=p.id,x=p.anchor.x,y=p.anchor.y,z=p.anchor.z,height=p.height,bend=p.bend} end
    end
    local nearest={};local minimum_gap=1e9;local overlaps=0
    for i,f in ipairs(s.fish) do
        local closest=1e9
        for j,n in ipairs(s.fish) do
            if i~=j then
                local d=length(f.x-n.x,f.y-n.y,f.z-n.z)
                closest=math.min(closest,d)
                local gap=d-f.half_length-n.half_length
                minimum_gap=math.min(minimum_gap,gap)
                if j>i and gap<0 then overlaps=overlaps+1 end
            end
        end
        nearest[#nearest+1]=closest
    end
    table.sort(nearest)
    local fins={}
    for _,name in ipairs({'root','tail_middle','peduncle','fin_left','fin_right','chest','head','shoulder_left','elbow_left','wrist_left','shoulder_right','elbow_right','wrist_right','hair_root','hair_tip'}) do
        local p=go.get_world_position(model.get_go('/player#model',name));fins[name]={x=p.x,y=p.y,z=p.z}
    end
    return {minimum_fish_gap=minimum_gap,fish_overlaps=overlaps,nearest_fish_p10=nearest[math.ceil(#nearest*.1)],nearest_fish_median=nearest[math.ceil(#nearest*.5)],maximum_fish_penetration=penetration,fish_samples=fish_samples,near_plants=plant_samples,drifters=#s.drifters,fish=#s.fish,plants=#s.plants,bubble_pool=#s.bubbles,active_bubbles=active,emitted=s.emitted,wake_emitted=s.wake_emitted,contacts=s.contacts,maximum_bend=max_bend,mean_fish_travel=travel/#s.fish,neighbor_pairs=s.neighbors,steps=s.step,clip=s.clip,phase=s.phase,bones=fins}
end
return M
