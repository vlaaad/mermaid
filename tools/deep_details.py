"""Discoverable archaeology down the slope, using shared low-poly assets."""
import math, random
from bathymetry import mesh_height

def amphora(Mesh):
    m=Mesh();clay=(.48,.31,.19)
    levels=[(0,.14),(.12,.24),(.45,.36),(.75,.30),(.88,.13),(1.05,.12),(1.07,.17),(1.12,.17),(1.12,.115),(.96,.09)]
    rings=[]
    for y,r in levels:rings.append([(r*math.cos(a*math.tau/16),y,r*math.sin(a*math.tau/16)) for a in range(16)])
    for i in range(len(rings)-1):
        for j in range(16):m.quad(rings[i][j],rings[i+1][j],rings[i+1][(j+1)%16],rings[i][(j+1)%16],clay if i<7 else (.24,.16,.11))
    for side in [-1,1]:
        m.tube([(side*.14,1.01,0),(side*.33,.98,0),(side*.39,.81,0),(side*.30,.64,0)],[.035]*4,clay,7)
    return m

def populate(place):
    rng=random.Random(9274);landmarks=[];platforms=[]
    def ground(asset,x,z,scale=1,yaw=0,**kwargs):
        y=mesh_height(x,z)
        for cx,cz,sx,sz,top in platforms:
            if abs(x-cx)<sx*.5 and abs(z-cz)<sz*.5:y=max(y,top)
        place(asset,(x,y-.10,z),scale,yaw,**kwargs);return y
    # Follow the ledge contour, with buried masonry foundations. Columns on
    # the steep descent itself looked like floating poles against a dark wall.
    for i in range(5):
        x=-28+i*4;z=33
        top=max(mesh_height(x+dx,z+dz) for dx in [-2,0,2] for dz in [-4,0,4])+.25
        bottom=min(mesh_height(x+dx,z+dz) for dx in [-2,0,2] for dz in [-4,0,4])-1
        place('plinth',(x,top,z),(4.1,(top-bottom)/.8,8.0))
        platforms.append((x,z,4.1,8.0,top))
        for side in [-1,1]:
            place('column',(x,top,33+side*2.6),(.48,.45+rng.random()*.2,.48),.12)
    ground('arch',-8,33,.85,math.pi/2)
    for side in [-1,1]:ground('sponge',-20,33+side*3.5,1.3)
    landmarks.append(dict(name='Broken processional avenue',position=[-20,mesh_height(-20,33)+5,33]))
    # A lower circular sanctuary, open above and with generous swim-throughs.
    cx,cz=24,68;cy=mesh_height(cx,cz)
    for i in range(8):
        a=i*math.tau/8;x=cx+7*math.cos(a);z=cz+7*math.sin(a)
        ground('column',x,z,(.58,.95,.58),-a)
        ground('rock0',x,z,(1.2,1.0,1.2),a)
    ground('ring',cx,cz,1.05,.1)
    ground('rock1',cx,cz,(3,1.0,2.6),.12)
    for i in range(14):
        a=rng.random()*math.tau;r=rng.uniform(3,10)
        ground(rng.choice(['sponge','coral_blue','coral_pink']),cx+math.cos(a)*r,cz+math.sin(a)*r,rng.uniform(.6,1.4),a)
    landmarks.append(dict(name='Drowned circular sanctuary',position=[cx,cy+5,cz]))
    # A shattered gateway and pottery cargo in the opposite side of the basin.
    cx,cz=-25,70
    ground('gateway_facade',cx,cz,(.8,.8,.8),-.35)
    for i in range(8):
        x=cx+rng.uniform(-7,10);z=cz+rng.uniform(-6,5)
        ground('rock'+str(i%4),x,z,(rng.uniform(.7,1.7),rng.uniform(.5,1.3),rng.uniform(.7,1.5)),rng.random()*math.tau)
    landmarks.append(dict(name='Buried gateway and pottery cargo',position=[cx,mesh_height(cx,cz)+4,cz]))
    for cx,cz in [(-20,33),(24,68),(-25,70),(2,62)]:
        for i in range(7):
            ground('amphora',cx+rng.uniform(-2,2),cz+rng.uniform(-2,2),rng.uniform(.65,1.15),rng.random()*math.tau)
        for i in range(5):ground('kelp',cx+rng.uniform(-8,8),cz+rng.uniform(-5,5),rng.uniform(.6,1.1),rng.random()*math.tau)
    # Current-following schools create movement between the deep landmarks.
    for cx,cz in [(24,68),(-25,70)]:
        for i in range(14):
            x=cx+rng.gauss(0,2);z=cz+rng.gauss(0,2)
            place('fish_blue',(x,mesh_height(x,z)+rng.uniform(4,8),z),rng.uniform(.5,.8),.2)
    # Small habitats along the descent and around the lower discoveries. Each
    # has several distinct, current-responsive plants and its own loose school.
    for site,(cx,cz) in enumerate([(-17,42),(13,46),(-17,76),(22,79)]):
        for i in range(3):
            a=i*math.tau/3+site*.7
            ground('ribbon_kelp' if i==1 else 'kelp',cx+math.cos(a)*3,cz+math.sin(a)*2,
                   rng.uniform(.85,1.35),a,label=f'deep_garden_{site}_plant_{i}')
            ground(['coral_pink','sponge','coral_gold'][i],cx+math.cos(a)*1.6,cz+math.sin(a)*1.4,
                   rng.uniform(.9,1.6),a,label=f'deep_garden_{site}_coral_{i}')
        for i in range(5):
            # Distributed starting positions preserve the schools' body space.
            x=cx+(i%3-1)*2.2;z=cz+(i//3-.5)*2.2
            place('fish_silver' if site%2 else 'fish_blue',(x,mesh_height(x,z)+4+(i%3)*.8,z),
                  rng.uniform(.6,.85),site*.7,label=f'deep_garden_{site}_fish_{i}')
    return landmarks
