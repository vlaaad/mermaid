"""Deterministic, editable geometry source. Emit shared glTF meshes and world layout.

Coordinates: meters, Y up, swimming forward -Z. Seed 73. No external assets.
Regenerate with python3 tools/build_assets.py. GLBs can be edited in Blender.
"""
import json
import math
from pathlib import Path
import random
import struct

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/generated"
R = random.Random(73)
STATS = {}


def vec(p):
    return np.array(p, dtype=float)


class Mesh:
    def __init__(self):
        self.p, self.n, self.c, self.uv = [], [], [], []

    def tri(self, a, b, c, color, uv=None, normals=None):
        a, b, c = vec(a), vec(b), vec(c)
        n = np.cross(b - a, c - a)
        length = np.linalg.norm(n)
        if length < 1e-9:
            return
        n = n / length
        self.p.extend([a, b, c])
        self.n.extend(normals if normals is not None else [n, n, n])
        self.c.extend([tuple(min(1,max(0,float(v))) for v in (*color[:3], color[3] if len(color) == 4 else 1))] * 3)
        self.uv.extend(uv or [(0, 0), (1, 0), (1, 1)])

    def quad(self, a, b, c, d, color, uv=None):
        uv = uv or [(0, 0), (1, 0), (1, 1), (0, 1)]
        self.tri(a, b, c, color, [uv[i] for i in [0, 1, 2]])
        self.tri(a, c, d, color, [uv[i] for i in [0, 2, 3]])

    def ellipsoid(self, center, radius, color, rings=12, sides=20):
        center, radius = vec(center), vec(radius)
        def point(i, j):
            a, b = math.pi * i / rings, 2 * math.pi * j / sides
            n = vec((math.sin(a) * math.cos(b), math.cos(a), math.sin(a) * math.sin(b)))
            normal = n / radius
            return center + radius * n, normal / np.linalg.norm(normal)
        for i in range(rings):
            for j in range(sides):
                points = [point(i, j), point(i + 1, j), point(i + 1, j + 1), point(i, j + 1)]
                for indices in ([0, 1, 2], [0, 2, 3]):
                    self.tri(*(points[k][0] for k in indices), color,
                             normals=[points[k][1] for k in indices])

    def tube(self, centers, radii, color, sides=12, caps=True):
        centers = [vec(p) for p in centers]
        rings, normals = [], []
        for i, (p, radius) in enumerate(zip(centers, radii)):
            tangent = centers[min(i + 1, len(centers) - 1)] - centers[max(0, i - 1)]
            tangent /= max(np.linalg.norm(tangent), 1e-9)
            right = np.cross(tangent, vec((0, 0, 1)))
            if np.linalg.norm(right) < .01:
                right = np.cross(tangent, vec((0, 1, 0)))
            right /= np.linalg.norm(right)
            front = np.cross(right, tangent)
            rx, rz = radius if isinstance(radius, tuple) else (radius, radius)
            ring, ns = [], []
            for j in range(sides):
                a = 2 * math.pi * j / sides
                radial = math.cos(a) * right * rx + math.sin(a) * front * rz
                ring.append(p + radial)
                outward=math.cos(a)*right/max(rx,1e-6)+math.sin(a)*front/max(rz,1e-6)
                ns.append(outward / max(np.linalg.norm(outward), 1e-9))
            rings.append(ring)
            normals.append(ns)
        for i in range(len(rings) - 1):
            for j in range(sides):
                jj = (j + 1) % sides
                positions = [rings[i][j], rings[i][jj], rings[i + 1][jj], rings[i + 1][j]]
                ns = [normals[i][j], normals[i][jj], normals[i + 1][jj], normals[i + 1][j]]
                for indices in ([0, 1, 2], [0, 2, 3]):
                    self.tri(*(positions[k] for k in indices), color, normals=[ns[k] for k in indices])
        if caps:
            for j in range(sides):
                jj = (j + 1) % sides
                self.tri(centers[0], rings[0][jj], rings[0][j], color)
                self.tri(centers[-1], rings[-1][j], rings[-1][jj], color)

    def box(self, center, size, color, bevel=.12):
        x, y, z = center
        w, h, d = np.array(size) / 2
        # Octagonal bevelled blocks retain broad faces instead of triangulated noise.
        ring = [(-w+bevel,-d), (w-bevel,-d), (w,-d+bevel), (w,d-bevel),
                (w-bevel,d), (-w+bevel,d), (-w,d-bevel), (-w,-d+bevel)]
        levels = []
        for yy, shrink in [(-h,.92),(-h+bevel,1),(h-bevel,1),(h,.92)]:
            levels.append([(x+px*shrink,y+yy,z+pz*shrink) for px,pz in ring])
        for i in range(3):
            for j in range(8):
                jj=(j+1)%8
                self.quad(levels[i][j],levels[i+1][j],levels[i+1][jj],levels[i][jj],color)
        for j in range(8):
            jj=(j+1)%8
            self.tri((x,y+h,z),levels[-1][jj],levels[-1][j],color)
            self.tri((x,y-h,z),levels[0][j],levels[0][jj],color)

    def save(self, name, category="stone"):
        binary = bytearray()
        views, accessors = [], []
        for values, kind in [(self.p,"VEC3"),(self.n,"VEC3"),(self.c,"VEC4"),(self.uv,"VEC2")]:
            a = np.asarray(values, dtype="<f4")
            view = {"buffer":0,"byteOffset":len(binary),"byteLength":a.nbytes,"target":34962}
            binary.extend(a.tobytes())
            views.append(view)
            accessor = {"bufferView":len(views)-1,"componentType":5126,"count":len(a),"type":kind}
            if len(accessors)==0:
                accessor.update(min=a.min(axis=0).tolist(),max=a.max(axis=0).tolist())
            accessors.append(accessor)
        doc={"asset":{"version":"2.0","generator":"Mermaid deterministic asset source"},
             "scene":0,"scenes":[{"nodes":[0]}],"nodes":[{"mesh":0,"name":name}],
             "meshes":[{"name":name,"primitives":[{"attributes":{"POSITION":0,"NORMAL":1,"COLOR_0":2,"TEXCOORD_0":3},"material":0}]}],
             "materials":[{"name":"reef","pbrMetallicRoughness":{"baseColorFactor":[1,1,1,1],"metallicFactor":0,"roughnessFactor":.8}}],
             "buffers":[{"byteLength":len(binary)}],"bufferViews":views,"accessors":accessors}
        encoded=json.dumps(doc,separators=(',',':')).encode()
        encoded += b' ' * (-len(encoded)%4)
        payload=struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
        (OUT/f'{name}.glb').write_bytes(struct.pack('<III',0x46546c67,2,12+len(payload))+payload)
        sampler='scene_texture' if category=='blit' else 'caustics'
        texture=f' textures {{ sampler: "{sampler}" texture: "/assets/generated/caustics.png" }}\n'
        if category!='blit':texture+=' textures { sampler: "stone_detail" texture: "/assets/textures/limestone-v1.png" }\n'
        (OUT/f'{name}.model').write_text(f'mesh: "/assets/generated/{name}.glb"\nmaterials {{\n name: "reef"\n material: "/render/{category}.material"\n{texture}}}\n')
        (OUT/f'{name}.go').write_text(f'components {{ id: "model" component: "/assets/generated/{name}.model" position {{ x:0 y:0 z:0 }} rotation {{x:0 y:0 z:0 w:1}} }}\n')
        STATS[name]={"triangles":len(self.p)//3,"bytes":12+len(payload)}


def make_rock(seed):
    rng = random.Random(seed)
    m=Mesh()
    # Irregular rectangular strata, chipped edges and uneven caps; shared instances remain editable.
    outline=[(-.85,-1),(-.25,-1.02),(.75,-1),(1,-.74),(1.02,-.1),(1,.78),(.74,1),(.12,1.03),(-.80,1),(-1,.70),(-1.03,.04),(-1,-.74)]
    outline=[(x*rng.uniform(.88,1.10),z*rng.uniform(.88,1.10)) for x,z in outline]
    rings=[]
    for level,(y,shrink) in enumerate([(-.5,.90),(-.40,1),(.24,1.01),(.44,.98),(.5,.88)]):
        rings.append([(x*shrink+rng.uniform(-.035,.035),y+rng.uniform(-.065,.065),z*shrink+rng.uniform(-.035,.035)) for x,z in outline])
    col=(.18,.31,.44)
    for i in range(len(rings)-1):
        for j in range(len(outline)):
            jj=(j+1)%len(outline)
            v=rng.uniform(.80,1.16)
            m.quad(rings[i][j],rings[i+1][j],rings[i+1][jj],rings[i][jj],tuple(c*v for c in col))
    for j in range(len(outline)):
        jj=(j+1)%len(outline)
        m.tri((.02,.49,-.03),rings[-1][jj],rings[-1][j],(.25,.39,.54))
        m.tri((0,-.5,0),rings[0][j],rings[0][jj],col)
    return m


def column():
    m=Mesh()
    stone=(.25,.38,.41)
    m.box((0,.22,0),(2.0,.44,2.0),stone,.13)
    m.box((0,.57,0),(1.68,.25,1.68),stone,.1)
    for drum in range(6):
        lo=.73+drum*1.15
        rings=[]
        for y,r in [(lo,.68),(lo+.08,.72),(lo+1.08,.70),(lo+1.13,.67)]:
            rings.append([(math.cos(j*math.tau/32)*r*(1+.055*math.cos(j*math.pi)),y,math.sin(j*math.tau/32)*r*(1+.055*math.cos(j*math.pi))) for j in range(32)])
        for i in range(3):
            for j in range(32):
                jj=(j+1)%32
                m.quad(rings[i][j],rings[i+1][j],rings[i+1][jj],rings[i][jj],stone)
    m.box((0,7.78,0),(1.65,.4,1.65),stone,.08)
    m.box((0,8.11,0),(2.0,.3,2.0),stone,.1)
    return m


def arch():
    m=Mesh()
    col=(.25,.38,.41)
    for side in [-1,1]:
        for j in range(5):
            m.box((side*2.2,.5+j*.98,0),(1.05,.96,1.3),col,.09)
    for j in range(13):
        a,b=j*math.pi/13+.012,(j+1)*math.pi/13-.012
        pts=[]
        for z in [-.65,.65]:
            pts.extend([(r*math.cos(t),4.7+r*math.sin(t),z) for r,t in [(1.68,a),(2.73,a),(2.73,b),(1.68,b)]])
        for ids in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:
            m.quad(*(pts[k] for k in ids),col)
    return m


def ring_ruin():
    m=Mesh()
    for j in range(22):
        a,b=j*math.tau/22+.012,(j+1)*math.tau/22-.012
        pts=[]
        for z in [-.50,.50]:
            pts.extend([(r*math.cos(t),r*math.sin(t),z) for r,t in [(3.65,a),(4.45,a),(4.45,b),(3.65,b)]])
        for ids in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:
            m.quad(*(pts[k] for k in ids),(.28,.41,.42))
    return m


def kelp():
    m=Mesh()
    rng=random.Random(315)
    for stalk in range(2):
        x=rng.uniform(-.18,.18); z=rng.uniform(-.18,.18); height=rng.uniform(4.5,7.0)
        centers=[(x+.13*math.sin(i*.6+stalk),i*height/9,z+.1*math.sin(i*.5)) for i in range(10)]
        m.tube(centers,[.022]*10,(.15,.29,.10),sides=5)
        for side in [-1,1]:
            for leaf in range(6):
                base=(leaf+.7)*height/9
                length=rng.uniform(1.05,1.65)
                a=rng.uniform(-.5,.5)
                for j in range(3):
                    t0,t1=j/3,(j+1)/3
                    def p(t,s):
                        breadth=math.sin(t*math.pi)*.12
                        return (x+side*t*.32+math.sin(base)*.11+s*breadth,base+t*length,z+a*t+math.sin(t*math.pi)*.16+s*breadth*.5)
                    color=(.21+rng.random()*.035,.34+leaf*.008,.08)
                    uv=[(0,base/height),(1,base/height),(1,(base+length)/height),(0,(base+length)/height)]
                    m.quad(p(t0,-1),p(t0,1),p(t1,1),p(t1,-1),color,uv)
    return m


def ribbon_kelp():
    m=Mesh()
    for blade in range(4):
        angle=blade*1.8
        length=3.6+blade*.7
        for j in range(14):
            def p(t,side):
                width=math.sin(math.pi*t)*(.22+blade*.045)
                return (math.sin(t*2.0+angle)*t*.6+side*width,t*length,math.cos(angle)*t*t*.8+side*width*math.sin(t*3+angle))
            a,b=j/14,(j+1)/14
            m.quad(p(a,-1),p(a,1),p(b,1),p(b,-1),(.16,.28,.10))
    return m


def coral(color,sponges=False):
    m=Mesh()
    for branch in range(9):
        x,z=R.uniform(-.7,.7),R.uniform(-.45,.45)
        h=R.uniform(.45,1.3)
        if sponges:
            rings=[]
            for y,r in [(0,.15),(h,.23),(h-.08,.14),(.05,.10)]:
                rings.append([(x+r*math.cos(j*math.tau/10),y,z+r*math.sin(j*math.tau/10)) for j in range(10)])
            for i in range(3):
                for j in range(10):
                    jj=(j+1)%10
                    m.quad(rings[i][j],rings[i][jj],rings[i+1][jj],rings[i+1][j],color if i<2 else tuple(c*.35 for c in color))
        else:
            m.tube([(x,0,z),(x*.9,h*.5,z),(x+.15,h,z)], [.065,.06,.04],color,7)
            for side in [-1,1]:
                m.tube([(x,h*.4,z),(x+side*.25,h*.65,z),(x+side*.4,h*.9,z+.1)], [.045,.04,.023],color,6)
    return m


def fish():
    m=Mesh(); gold=(.91,.64,.09)
    m.ellipsoid((0,0,0),(.31,.16,.095),gold,4,8)
    m.tri((-.26,0,0),(-.49,.17,0),(-.49,-.17,0),(.98,.76,.17))
    m.tri((0,.12,0),(-.17,.27,0),(-.19,.08,0),(.78,.51,.04))
    m.ellipsoid((.20,.04,.083),(.024,.024,.016),(.025,.035,.045),3,5)
    m.ellipsoid((.20,.04,-.083),(.024,.024,.016),(.025,.035,.045),3,5)
    m.uv=[(max(-p[0],0),0) for p in m.p]
    return m


def ray():
    m=Mesh()
    m.ellipsoid((0,0,0),(.25,.07,.54),(.44,.61,.62),7,12)
    for side in [-1,1]:
        pts=[(0,.02,-.4),(side*.45,.08,-.25),(side*1.35,.17,.10),(side*.65,-.02,.48),(0,0,.35)]
        for j in range(1,len(pts)-1): m.tri(pts[0],pts[j],pts[j+1],(.40,.56,.58))
    m.tube([(0,0,.3),(0,-.03,.9),(0,-.12,1.6)],[.045,.02,.003],(.13,.24,.25),6)
    return m


def mermaid():
    m=Mesh(); skin=(.91,.64,.39)
    m.tube([(0,.12,.06),(0,.35,0),(0,.62,-.08),(0,.92,-.16),(0,1.21,-.22),(0,1.38,-.22)],[(.32,.20),(.29,.18),(.26,.16),(.33,.21),(.46,.21),(.40,.17)],skin,24)
    m.tube([(0,1.31,-.22),(0,1.64,-.25)],[.14,.13],skin,16)
    m.ellipsoid((0,1.92,-.24),(.32,.41,.30),skin,16,24)
    m.ellipsoid((0,1.91,-.525),(.045,.075,.065),skin,7,10)
    for side in [-1,1]:
        m.ellipsoid((side*.12,2.005,-.510),(.065,.042,.018),(.91,.92,.85),6,10)
        m.ellipsoid((side*.12,2.005,-.528),(.024,.031,.009),(.035,.19,.22),5,8)
        m.tube([(side*.07,2.09,-.49),(side*.13,2.11,-.49),(side*.19,2.08,-.47)],[.012,.015,.009],(.37,.24,.10),5)
    m.tube([(-.07,1.79,-.51),(0,1.78,-.542),(.07,1.79,-.51)],[.013,.02,.013],(.67,.31,.29),6)
    # Turquoise bodice and thin gold edging, visible from the trailing camera.
    m.tube([(0,.89,-.14),(0,1.02,-.18),(0,1.17,-.21)],[(.34,.217),(.39,.224),(.443,.221)],(.075,.40,.40),24)
    m.tube([(0,.88,-.14),(0,.91,-.15)],[(.345,.222),(.353,.223)],(.81,.66,.28),24)
    for side in [-1,1]:
        wrist=(side*(1.48 if side<0 else 1.30),.56 if side<0 else .28,-.53)
        m.tube([(side*.4,1.22,-.22),(side*.72,1.04,-.19),(side*1.03,.82 if side<0 else .65,-.32),wrist],[.14,.13,.095,.065],skin,14)
        palm=(wrist[0]+side*.045,wrist[1]-.10,wrist[2]-.02)
        m.ellipsoid(palm,(.10,.14,.060),skin,8,12)
        for finger in range(4):
            x=palm[0]+(finger-1.5)*.045
            length=.10+.035*math.sin((finger+.5)*math.pi/4)
            m.tube([(x,palm[1]-.08,palm[2]),(x+side*.018,palm[1]-.08-length,palm[2]-.03)],[.023,.014],skin,6)
        # Gold shoulder clasp and thin strap.
        m.tube([(side*.31,1.08,-.01),(side*.33,1.38,-.19),(side*.32,1.15,-.43)],[.026,.026,.026],(.77,.63,.28),8)
    tail_centers=[(0,.16,.05),(0,-.18,.17),(-.05,-.56,.43),(-.13,-.96,.72),(-.20,-1.32,1.03),(-.25,-1.63,1.32),(-.25,-1.86,1.57)]
    m.tube(tail_centers,[(.34,.23),(.37,.25),(.34,.23),(.28,.19),(.21,.15),(.14,.11),(.10,.08)],(.055,.57,.50),32)
    for side in [-1,1]:
        for i in range(12):
            u0,u1=i/12,(i+1)/12
            def fin(u,v):
                return (-.25+side*(.08+u*.92)*v,-1.80-v*(.55+.62*math.sin(u*math.pi*.85)),1.58+v*(.22+.35*u))
            for j in range(6):
                v0,v1=j/6,(j+1)/6
                col=(.22+.32*v1,.72+.13*v1,.61-.20*v1)
                m.quad(fin(u0,v0),fin(u1,v0),fin(u1,v1),fin(u0,v1),col)
            m.tube([fin((u0+u1)/2,v) for v in [0,.25,.5,.75,1]],[.008]*5,(.56,.85,.50),5)
    # Sculpted cap and tapered locks streaming backward in the water.
    m.ellipsoid((0,2.04,-.16),(.335,.335,.29),(.79,.51,.19),12,24)
    # Separate undulating locks have open silhouettes instead of a solid ponytail cone.
    m.tube([(0,2.0,.00),(0,1.8,.01),(-.13,1.60,.14),(-.33,1.45,.26),(-.57,1.26,.50)],[(.29,.16),(.31,.17),(.28,.15),(.24,.12),(.02,.02)],(.82,.59,.25),18)
    hair_rng=random.Random(184)
    for strand in range(46):
        a=hair_rng.random()*math.tau
        phase=hair_rng.random()*math.tau
        root=(math.cos(a)*.26,2.12+math.sin(a)*.15,-.08+math.sin(a)*.13)
        length=hair_rng.uniform(1.15,2.15)
        centers=[]
        for j in range(13):
            t=j/12
            centers.append((root[0]-t*.80-math.sin(t*math.pi/2)*length*.30+math.sin(t*5+phase)*.19*t,
                            root[1]-t*length*.72+math.sin(t*6+phase)*.25*t,
                            root[2]+t*length*.58+math.sin(t*8+phase)*.18*t))
        shade=hair_rng.uniform(.86,1.14)
        width=.13 if strand%3==0 else .042
        m.tube(centers,[(width*(1-j/12)**.65+.002,.060*(1-j/12)+.002) for j in range(13)],(.91*shade,.67*shade,.28*shade),7)
    # Preserve the world seed stream used by the previous 38-lock authoring pass.
    for _ in range(76):R.random()
    return m


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    settings=json.loads((ROOT/'assets/art.json').read_text())
    def lua(value):
        if isinstance(value,dict):return '{'+','.join(k+'='+lua(v) for k,v in value.items())+'}'
        if isinstance(value,list):return '{'+','.join(lua(v) for v in value)+'}'
        return json.dumps(value)
    (ROOT/'main/art.lua').write_text('-- Generated from assets/art.json; edit that source.\nreturn '+lua(settings)+'\n')
    for i in range(4): make_rock(100+i).save(f'rock{i}')
    column().save('column')
    arch().save('arch')
    ring_ruin().save('ring')
    kelp().save('kelp','kelp')
    for _ in range(189):R.random()
    ribbon_kelp().save('ribbon_kelp','kelp')
    coral((.56,.27,.51),True).save('sponge','stone')
    coral((.84,.39,.41)).save('coral_pink','stone')
    coral((.28,.39,.72)).save('coral_blue','stone')
    fish().save('fish','fish')
    bluefish=fish()
    bluefish.c=[(.10,.28,.36,1) if c[0]>.1 else c for c in bluefish.c]
    bluefish.save('fish_blue','fish')
    ray().save('ray','ray')
    mermaid().save('mermaid','mermaid')
    ground=Mesh()
    for z in range(-125,21,4):
        for x in range(-60,61,4):
            def p(xx,zz): return (xx,-.25+.13*math.sin(xx*.3)*math.cos(zz*.19),zz)
            ground.quad(p(x,z),p(x,z+4),p(x+4,z+4),p(x+4,z),(.28,.52,.53))
    ground.save('seabed','sand')
    surface=Mesh()
    surface.quad((-130,48,35),(130,48,35),(130,48,-230),(-130,48,-230),(.12,.64,.83))
    surface.save('surface','surface')
    particle=Mesh()
    particle.ellipsoid((0,0,0),(.025,.025,.025),(.38,.74,.80),3,4)
    particle.save('particle','dust')
    fullscreen=Mesh()
    fullscreen.quad((-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0),(1,1,1))
    fullscreen.save('fullscreen','blit')

    # Seamless cellular caustics. One shared texture, two scrolling samples per pixel.
    rng=np.random.default_rng(73)
    yy,xx=np.mgrid[0:256,0:256]/256*7
    # Periodic refraction warp bends cellular edges into flowing caustic ribbons.
    xx0,yy0=xx.copy(),yy.copy()
    xx=(xx0+.24*np.sin(yy0*math.tau/7*3+.4*np.sin(xx0*math.tau/7*2))+.10*np.sin(yy0*math.tau/7*5))%7
    yy=(yy0+.22*np.sin(xx0*math.tau/7*2+.5*np.cos(yy0*math.tau/7*3)))%7
    nearest=np.full((256,256),1e6); second=nearest.copy()
    for i in range(7):
        for j in range(7):
            px,py=i+rng.random(),j+rng.random()
            dx=np.abs(xx-px);dx=np.minimum(dx,7-dx)
            dy=np.abs(yy-py);dy=np.minimum(dy,7-dy)
            d=dx*dx+dy*dy
            second=np.minimum(second,np.maximum(nearest,d));nearest=np.minimum(nearest,d)
    intensity=np.exp(-(np.sqrt(second)-np.sqrt(nearest))*29)
    Image.fromarray(np.uint8(np.clip(intensity,0,1)*255)).save(OUT/'caustics.png')

    objects=[]; obstacles=[]
    placements=0
    def place(asset,p,scale=(1,1,1),yaw=0,collision=False):
        nonlocal placements
        name=f'{asset}_{placements:04d}'
        placements+=1
        if isinstance(scale,(int,float)):scale=(scale,)*3
        q=(0,math.sin(yaw/2),0,math.cos(yaw/2))
        objects.append(f'instances {{ id: "{name}" prototype: "/assets/generated/{asset}.go" position {{x:{p[0]} y:{p[1]} z:{p[2]}}} rotation {{x:{q[0]} y:{q[1]} z:{q[2]} w:{q[3]}}} scale3 {{x:{scale[0]} y:{scale[1]} z:{scale[2]}}} }}')
        if collision:
            obstacles.append([round(v,3) for v in [p[0],p[1],p[2],scale[0]*.88,scale[1]*.48,scale[2]*.88]])
        if asset=='column':
            obstacles.append([p[0],p[1]+4.2*scale[1],p[2],.76*scale[0],4.2*scale[1],.76*scale[2]])
        elif asset=='arch':
            for side in [-1,1]:
                obstacles.append([p[0]+side*2.2*scale[0],p[1]+2.5*scale[1],p[2],.56*scale[0],2.5*scale[1],.67*scale[2]])
            obstacles.append([p[0],p[1]+7*scale[1],p[2],2.5*scale[0],.6*scale[1],.67*scale[2]])
        elif asset=='ring':
            for j in range(22):
                a=(j+.5)*math.tau/22
                obstacles.append([p[0]+math.cos(a)*4.05*scale[0],p[1]+math.sin(a)*4.05*scale[1],p[2],.62*scale[0],.62*scale[1],.55*scale[2]])
    def at_screen(u,v,z):
        # Authoring aid only: emit a fixed 3D coordinate. No runtime camera-facing backdrop.
        root=np.array([-1,4.8,4.0]);pitch=-.04
        eye=root+np.array([settings['eye_right'],settings['eye_height']-math.sin(pitch)*settings['camera_distance'],math.cos(pitch)*settings['camera_distance']])
        target=root+np.array([settings['look_right'],settings['look_height']+math.sin(pitch)*16,-16])
        forward=target-eye;forward/=np.linalg.norm(forward)
        right=np.cross(forward,[0,1,0]);right/=np.linalg.norm(right)
        up=np.cross(right,forward)
        ray=forward+right*((u-.5)*2*math.tan(math.radians(59)/2)*16/9)+up*((.5-v)*2*math.tan(math.radians(59)/2))
        return tuple(eye+ray*((z-eye[2])/ray[2]))
    place('seabed',(0,0,0))
    place('surface',(0,0,0))
    # Terraces of broad weathered rock frame a navigable central canyon.
    dense=settings.get('dense_terrain',False)
    for side in [-1,1]:
        for tier in range(6 if dense else 4):
            for k in range(26 if dense else 15):
                z=12-k*(4.2 if dense else 7)+R.uniform(-.8,.8)
                x=side*(12+tier*(3 if dense else 4)+2*math.sin(z*.12)) if side>0 else -(10+tier*(2.4 if dense else 3)+2*math.sin(z*.12))
                if side==1:x+=1.8
                y=tier*((3.0 if side>0 else 2.7) if dense else (4.4 if side>0 else 3.8))+R.uniform(-.2,.3)
                scale=(R.uniform(2.0,3.2),R.uniform(2.0,3.1),R.uniform(1.8,3.1)) if dense else (R.uniform(3.2,5.5),R.uniform(2.6,4.4),R.uniform(3.0,5.3))
                place(f'rock{R.randrange(4)}',(x,y,z),scale,R.uniform(-.28,.28),True)
                if tier>0:
                    height=y+scale[1]*.5+.6
                    place(f'rock{(tier+k)%4}',(x,y-height*.5,z),(scale[0]*.91,height,scale[2]*.91),0,True)
                if dense and tier>3 and k<18 and R.random()<.30:
                    place('kelp',(x,y+scale[1]*.5,z),R.uniform(.75,1.15),R.random()*math.tau)
                if tier<3 and k<11:
                    for _ in range(2):
                        place('kelp',(x+R.uniform(-2,2),y+scale[1]*.45,z+R.uniform(-2,2)),R.uniform(.65,1.3),R.random()*math.tau)
                    if R.random()<.85:place(R.choice(['sponge','coral_pink','coral_blue']),(x+R.uniform(-2,2),y+scale[1]*.5,z),R.uniform(.7,1.4))
    for k in range(32):
        x=R.uniform(-12,12);z=R.uniform(-90,2)
        if abs(x)<3.8 and z>-35:continue
        sy=R.uniform(.7,3.2)
        place(f'rock{R.randrange(4)}',(x,sy*.35,z),(R.uniform(.6,2.3),sy,R.uniform(.6,2)),R.random()*math.tau,True)
        if k%2==0:place('kelp',(x,sy*.8,z),R.uniform(.6,1))
    # Vertical architectural rhythm, farther silhouettes rise into the light.
    for side in [-1,1]:
        for k in range(8):
            z=-14-k*12
            x=side*(8+R.uniform(0,6))
            base=R.uniform(.7,5)
            scale=(R.uniform(.8,1.3),R.uniform(1.3,2.8),R.uniform(.8,1.3))
            # Keep the opening light well clear; foreground pillars were masking the ring.
            if k==0:
                x=side*14
                z-=8
                scale=(scale[0],1.25,scale[2])
            if not (side==1 and k in (0,1,2)):place('column',(x,base,z),scale,0)
    place('rock1',(2,.65,-15),(1.6,1.9,1.3),.3,True)
    place('rock2',(-2,.35,-23),(2.1,1.1,1.4),-.2,True)
    place('column',(4.8,0,-26),(.55,.42,.55))
    place('arch',(4.8,1.5,-45),(.9,.9,.9))
    place('arch',(21,4,-43),(2.35,1.55,2))
    place('ring',(22,21.6,-44),(1.15,1.15,1.15))
    for side in [-1,1]:
        place('column',(22+side*6.6,13.0,-44),(1.1,1.7,1.1))
        place('rock2',(22+side*6.5,18.5,-44),(1.5,10.5,1.5),0,True)
    place('rock1',(22,27,-44),(7.5,1.0,1.6))
    place('arch',(-13,5,-68),(2,2,2))
    place('column',(9.4,10,-43),(1.25,2.25,1.25))
    place('rock0',(9.4,7,-43),(3,6,3),0,True)
    place('column',(-8.6,3,-40),(1.1,1.7,1.1))
    for layer in range(6):
        for part in [-1,1]:
            place(f'rock{(layer+part)%4}',(-34+part*3.0,14+layer*3.2,-50),(3.4,3.0,3.8),part*.08,True)
    place('rock0',(29.5,29.3,-54),(7,.9,3.5))
    place('column',(25.5,30,-54),(1.5,1.9,1.5))
    place('column',(33.5,30,-54),(1.5,1.9,1.5))
    place('rock0',(29.5,45.8,-54),(7,.75,2.8))
    # Broken column bases and interlocking floor terraces leave a swimming route at X=-1.
    place('column',(1.7,-5.2,0),(.85,1.0,.85))
    for asset,pos,scale in [
        ('rock1',(2.5,.8,-3),(2.0,2.0,1.8)),
        ('rock2',(3.5,.9,-8),(2.4,2.7,2.1)),
        ('rock0',(3.5,2.5,-8),(1.4,1.4,1.4)),
        ('rock3',(-4.5,1.4,-9),(2.5,3.4,2.8)),
        ('rock1',(-4.4,3.7,-10),(2.0,1.4,2.0)),
        ('rock2',(1.8,.9,-20),(2.1,2.4,2.2)),
        ('rock0',(5.2,2.1,-24),(2.6,4.5,2.3)),
        ('rock1',(-2,1.4,-32),(2.0,3.3,2.0))]:
        place(asset,pos,scale,.15,True)
    place('sponge',(3.2,2,-3),1.0)
    place('coral_pink',(-4.5,4.2,-9),.9)
    place('kelp',(6.5,2.5,-10),1.0,.3)
    # Sun shafts are integrated through water in the depth-aware post process.
    # Preserve RNG stream so this renderer change does not reshuffle the fish.
    for _ in range(8):R.uniform(1.2,2)
    # Shared fish geometry/material => one instanced batch per visible mesh.
    for school in [1,2,4]:
        cx,cy,cz=[(-7,8,-14),(3.8,16,-40),(10,4,-11),(-7,3,0),(13,9,-54)][school]
        for k in range(50 if school in [1,4] else 10):
            place('fish_blue' if school in [1,4] else 'fish',(cx+R.gauss(0,2.2),cy+R.gauss(0,.7),cz+R.gauss(0,1.5)),R.uniform(.45,.8) if school in [1,4] else R.uniform(.8,1.4),.1*school)
    for k,(u,v,scale) in enumerate([(.10,.42,.46),(.055,.47,.64),(.15,.46,.47),(.13,.52,.43),(.06,.54,.40)]):
        p=list(at_screen(u,v,5.5))
        # Compensate the known opening-time local drift; these remain independent fish GOs.
        yaw=0 if k%3 else math.pi
        p[0]-=math.sin(3*.18+5.5*.12)*1.1*scale*math.cos(yaw)
        p[1]-=math.sin(3*.8+5.5)*.12*scale
        place('fish',p,scale,yaw)
    place('ray',at_screen(.33,.16,-18),2.2,-.5)
    place('ray',at_screen(.47,.23,-39),1.5,.3)
    place('ribbon_kelp',at_screen(.08,1.10,5),1.0,.3)
    place('sponge',at_screen(.94,.98,5),.85)
    place('coral_pink',at_screen(.98,.77,4),1.1)
    place('coral_pink',at_screen(.28,.80,2),1.0)
    place('sponge',at_screen(.10,.95,2),.70)
    for k in range(65):place('particle',(R.uniform(-15,15),R.uniform(1,22),R.uniform(-55,10)),R.uniform(.5,1.6))
    # Remove only obsolete outputs from the abandoned mesh-baking experiment.
    for stale in list(OUT.glob('ruins_chunk_*')) + [OUT/(n+ext) for n in ('fish_field','fish_blue_field','dust_field') for ext in ('.glb','.model','.go')]:
        if stale.suffix in ('.glb','.model','.go') and stale.exists():stale.unlink()
    (ROOT/'main/world.collection').write_text('name: "world"\n'+ '\n'.join(objects)+'\n')
    (ROOT/'main/obstacles.lua').write_text('return '+str(obstacles).replace('[','{').replace(']','}')+'\n')
    STATS['world']={"instances":len(objects),"source_placements":placements,"collision_boxes":len(obstacles),"seed":73}
    (OUT/'manifest.json').write_text(json.dumps(STATS,indent=2)+'\n')
    print(json.dumps(STATS,indent=2))


if __name__=='__main__':main()
