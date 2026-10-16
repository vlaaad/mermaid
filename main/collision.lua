-- Broad AABBs reject distant stone; convex planes follow the visible boulders.
local M={}
local obstacles=require 'main.obstacles'
local seafloor=require 'main.seafloor'
M.floor_height=seafloor.sample
local shape={
    {0,1.60,-.28,.37}, {0,.95,-.18,.35}, {0,.30,.06,.40},
    {0,-.40,.35,.35}, {-.18,-1.05,.95,.28}, {-.18,-1.95,1.40,.65}
}
function M.body(rotation)
    local body={minx=1e6,miny=1e6,minz=1e6,maxx=-1e6,maxy=-1e6,maxz=-1e6}
    for _,s in ipairs(shape) do
        local p=vmath.rotate(rotation,vmath.vector3((s[1]+.20)*.85,(s[2]-.22)*.85,s[3]*.85))
        local r=s[4]*.85
        body[#body+1]={p.x,p.y,p.z,r}
        body.minx=math.min(body.minx,p.x-r);body.maxx=math.max(body.maxx,p.x+r)
        body.miny=math.min(body.miny,p.y-r);body.maxy=math.max(body.maxy,p.y+r)
        body.minz=math.min(body.minz,p.z-r);body.maxz=math.max(body.maxz,p.z+r)
    end
    return body
end
local function clamp(v,a,b)return math.max(a,math.min(b,v))end
function M.resolve(position,body)
    local px,py,pz=position.x,position.y,position.z
    for _=1,6 do
        local deepest,nx,ny,nz=0,0,0,0
        for _,b in ipairs(obstacles) do
            if px+body.maxx>b[1]-b[4] and px+body.minx<b[1]+b[4]
            and py+body.maxy>b[2]-b[5] and py+body.miny<b[2]+b[5]
            and pz+body.maxz>b[3]-b[6] and pz+body.minz<b[3]+b[6] then
                for _,s in ipairs(body) do
                    local x,y,z=px+s[1],py+s[2],pz+s[3]
                    local gap,ax,ay,az
                    if b[7] then
                        local separation=-1e6
                        for _,plane in ipairs(b[7]) do
                            local d=x*plane[1]+y*plane[2]+z*plane[3]-plane[4]
                            if d>separation then separation=d;ax,ay,az=plane[1],plane[2],plane[3] end
                            if separation>=s[4] then break end
                        end
                        gap=s[4]-separation
                    else
                        local dx=x-clamp(x,b[1]-b[4],b[1]+b[4])
                        local dy=y-clamp(y,b[2]-b[5],b[2]+b[5])
                        local dz=z-clamp(z,b[3]-b[6],b[3]+b[6])
                        local distance=math.sqrt(dx*dx+dy*dy+dz*dz)
                        gap=s[4]-distance
                        if distance>.000001 then ax,ay,az=dx/distance,dy/distance,dz/distance
                        else
                            local ex=b[4]-math.abs(x-b[1]);local ey=b[5]-math.abs(y-b[2]);local ez=b[6]-math.abs(z-b[3])
                            if ex<ey and ex<ez then ax,ay,az=x>b[1] and 1 or -1,0,0;gap=s[4]+ex
                            elseif ey<ez then ax,ay,az=0,y>b[2] and 1 or -1,0;gap=s[4]+ey
                            else ax,ay,az=0,0,z>b[3] and 1 or -1;gap=s[4]+ez end
                        end
                    end
                    if gap>deepest then deepest=gap;nx,ny,nz=ax,ay,az end
                end
            end
        end
        if py+body.miny< -4.0 then
            for _,s in ipairs(body) do
                local h,ax,ay,az=seafloor.sample(px+s[1],pz+s[3])
                local gap=s[4]-(py+s[2]-h)*ay
                if gap>deepest then deepest=gap;nx,ny,nz=ax,ay,az end
            end
        end
        if deepest<=.0001 then break end
        px=px+nx*(deepest+.001);py=py+ny*(deepest+.001);pz=pz+nz*(deepest+.001)
    end
    return vmath.vector3(clamp(px,-130,135),math.min(py,49-body.maxy),clamp(pz,-185,85))
end
return M
