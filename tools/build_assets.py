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
        self.n.extend([vec(v) / np.linalg.norm(v) if np.linalg.norm(v)>1e-8 else n for v in normals] if normals is not None else [n, n, n])
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
                normal = math.cos(a) * right / max(rx, 1e-6) + math.sin(a) * front / max(rz, 1e-6)
                ns.append(normal / max(np.linalg.norm(normal), 1e-9))
            rings.append(ring)
            normals.append(ns)
        # Surface derivatives include taper and curvature, unlike radial-only normals.
        for i in range(len(rings)):
            for j in range(sides):
                along=vec(rings[min(i+1,len(rings)-1)][j])-vec(rings[max(i-1,0)][j])
                across=vec(rings[i][(j+1)%sides])-vec(rings[i][(j-1)%sides])
                n=np.cross(along,across)
                if np.linalg.norm(n)>1e-8:
                    n/=np.linalg.norm(n)
                    if np.dot(n,normals[i][j])<0:n=-n
                    normals[i][j]=n
        for i in range(len(rings) - 1):
            for j in range(sides):
                jj=(j+1)%sides
                positions=[rings[i][j],rings[i][jj],rings[i+1][jj],rings[i+1][j]]
                ns=[normals[i][j],normals[i][jj],normals[i+1][jj],normals[i+1][j]]
                uv=[(j/sides,i/(len(rings)-1)),((j+1)/sides,i/(len(rings)-1)),((j+1)/sides,(i+1)/(len(rings)-1)),(j/sides,(i+1)/(len(rings)-1))]
                for indices in ([0,2,1],[0,3,2]):
                    self.tri(*(positions[k] for k in indices),color,uv=[uv[k] for k in indices],normals=[ns[k] for k in indices])
        if caps:
            for j in range(sides):
                jj=(j+1)%sides
                self.tri(centers[0],rings[0][j],rings[0][jj],color)
                self.tri(centers[-1],rings[-1][jj],rings[-1][j],color)

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
        (OUT/f'{name}.model').write_text(f'mesh: "/assets/generated/{name}.glb"\nmaterials {{\n name: "reef"\n material: "/render/{category}.material"\n{texture}}}\n')
        (OUT/f'{name}.go').write_text(f'components {{ id: "model" component: "/assets/generated/{name}.model" position {{ x:0 y:0 z:0 }} rotation {{x:0 y:0 z:0 w:1}} }}\n')
        STATS[name]={"triangles":len(self.p)//3,"bytes":12+len(payload)}


def make_rock(seed):
    # Broad fractured limestone slabs, with square shoulders rather than drums.
    rng=random.Random(seed); m=Mesh()
    outline=[(-.83,-.96),(.66,-1),(.98,-.66),(1,.64),(.70,.94),(-.69,1),(-1,.62),(-.98,-.60)]
    outline=[(x*rng.uniform(.92,1.08),z*rng.uniform(.92,1.08)) for x,z in outline]
    rings=[]
    crown=[rng.uniform(-.06,.06) for _ in outline]
    for y,scale in [(-.5,.90),(-.41,1),(.34,1),(.5,.88)]:
        rings.append([(x*scale,y+crown[j],z*scale) for j,(x,z) in enumerate(outline)])
    stone=(.18,.30,.38)
    for i in range(3):
        for j in range(8):
            jj=(j+1)%8
            shade=rng.uniform(.86,1.08)*(1.06 if i==2 else 1)
            m.quad(rings[i][j],rings[i+1][j],rings[i+1][jj],rings[i][jj],tuple(v*shade for v in stone))
    for j in range(8):
        m.tri((.1,.51,-.1),rings[-1][(j+1)%8],rings[-1][j],(.24,.38,.44))
        m.tri((0,-.5,0),rings[0][j],rings[0][(j+1)%8],stone)
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
    # A circular opening IN a masonry wall, not a floating torus.
    m=Mesh(); col=(.28,.40,.43)
    for j in range(28):
        a,b=j*math.tau/28+.004,(j+1)*math.tau/28-.004
        pts=[]
        for z in [-.6,.6]:
            for t,r in [(a,3.05),(a,None),(b,None),(b,3.05)]:
                r=r or 4.35/max(abs(math.cos(t)),abs(math.sin(t)))
                pts.append((r*math.cos(t),r*math.sin(t),z))
        for ids in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:
            m.quad(*(pts[k] for k in ids),tuple(v*(.95+.05*math.sin(j*2.1)) for v in col))
    return m


def kelp():
    m=Mesh(); rng=random.Random(622)
    for stalk in range(2):
        x=rng.uniform(-.27,.27);z=rng.uniform(-.26,.26);height=rng.uniform(4.5,6.3)
        def stem(y):return vec((x+.16*math.sin(y*.85+stalk),y,z+.13*math.sin(y*.65+stalk)))
        m.tube([stem(i*height/15) for i in range(16)],[.022*(1-i/18) for i in range(16)],(.16,.28,.075),6)
        for leaf in range(12):
            base=(leaf+.7)*height/14; side=1 if leaf%2 else -1
            length=rng.uniform(.60,1.0)*(1-.30*base/height)
            phase=rng.uniform(-.5,.5);origin=stem(base)
            def point(t,v):
                breadth=math.sin(math.pi*t)**.8*.115
                return origin+vec((side*(t*.32+math.sin(t*math.pi)*.06)+v*breadth,
                                   t*length,phase*t+math.sin(t*math.pi)*.11+v*breadth*.7))
            col=(.19+rng.random()*.025,.32+rng.random()*.08,.07)
            for j in range(7):
                t0,t1=j/7,(j+1)/7
                m.quad(point(t0,-1),point(t0,1),point(t1,1),point(t1,-1),col)
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
    m=Mesh(); skin=(.93,.66,.42)
    # Continuous waist, ribcage and shoulder profile; back is a curved volume.
    m.tube([(0,.10,.08),(0,.30,.02),(0,.51,-.05),(0,.74,-.10),(0,.98,-.17),(0,1.20,-.22),(0,1.32,-.23)],
           [(.35,.235),(.32,.205),(.27,.17),(.285,.185),(.36,.225),(.43,.225),(.35,.17)],skin,32)
    m.tube([(0,1.27,-.23),(0,1.59,-.28)],[.135,.12],skin,20)
    m.ellipsoid((0,1.85,-.29),(.29,.36,.275),skin,20,28)
    m.ellipsoid((0,1.83,-.55),(.038,.06,.055),skin,8,12)
    for side in [-1,1]:
        m.ellipsoid((side*.105,1.92,-.535),(.055,.033,.014),(.92,.94,.87),6,10)
        m.ellipsoid((side*.105,1.92,-.547),(.021,.026,.007),(.035,.19,.22),5,8)
    m.tube([(-.06,1.73,-.54),(0,1.72,-.56),(.06,1.73,-.54)],[.009,.014,.009],(.67,.31,.29),6)
    # Narrow swimsuit band leaves a readable back and shoulders.
    m.tube([(0,.91,-.15),(0,1.02,-.18),(0,1.12,-.20)],[(.341,.220),(.375,.231),(.415,.23)],(.06,.34,.31),32)
    m.tube([(0,.90,-.15),(0,.925,-.16)],[(.34,.225),(.35,.226)],(.70,.58,.27),24)
    for side in [-1,1]:
        # Open relaxed swimming arms; tapered joints and separate fingers.
        elbow=(side*.73,.77,-.18 if side<0 else -.28)
        wrist=(side*1.10,.35,-.28 if side<0 else -.53)
        m.tube([(side*.39,1.19,-.22),(side*.52,1.04,-.20),elbow,(side*.92,.55,wrist[2]+.05),wrist],
               [.135,.14,.103,.088,.055],skin,18)
        palm=(wrist[0]+side*.035,wrist[1]-.09,wrist[2]-.015)
        m.ellipsoid(palm,(.073,.115,.047),skin,10,14)
        for finger in range(4):
            x=palm[0]+(finger-1.5)*.033
            length=[.10,.14,.15,.12][finger]
            m.tube([(x,palm[1]-.055,palm[2]),(x+side*.012,palm[1]-.11,palm[2]-.01),(x+side*.02,palm[1]-.055-length,palm[2]+.008)],
                   [.020,.018,.011],skin,7)
        m.tube([(palm[0]-side*.055,palm[1]+.03,palm[2]),(palm[0]-side*.10,palm[1]-.015,palm[2]-.035),(palm[0]-side*.12,palm[1]-.065,palm[2]-.03)],[.026,.022,.012],skin,8)
        m.tube([(side*.31,1.08,-.01),(side*.33,1.34,-.20),(side*.30,1.14,-.43)],[.019]*3,(.17,.41,.32),8)
    # Full hips transition into an S-shaped muscular tail, then a narrow peduncle.
    centers=[(0,.14,.065),(.025,-.13,.16),(.015,-.43,.32),(-.06,-.72,.52),(-.20,-1.00,.72),(-.37,-1.24,.91),(-.49,-1.45,1.07),(-.51,-1.61,1.18)]
    radii=[(.355,.25),(.405,.275),(.385,.265),(.315,.225),(.245,.18),(.165,.125),(.10,.08),(.07,.055)]
    m.tube(centers,radii,(.045,.55,.43),40)
    # Two swept, pointed lobes. Curved outlines replace straight triangular fans.
    def bez(points,t):
        a,b,c,d=[vec(p) for p in points]
        return (1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d
    for side in [-1,1]:
        def fin(u,v):
            if u<.55:
                edge=bez([(0,-.47,.54),(.20,-.82,.59),(.55,-.84,.20),(.92,-1.25,-.04)],u/.55)
            else:
                edge=bez([(.92,-1.25,-.04),(.84,-.66,-.10),(.43,-.08,-.045),(0,0,0)],(u-.55)/.45)
            q=vec((-.51,-1.59,1.18))+vec((side*edge[0],edge[1],edge[2]))*v
            q[2]+=.10*math.sin(v*math.pi)*math.sin(u*math.pi)+.018*math.sin(u*math.pi*24)*v*v
            return q
        def fn(u,v):
            u=max(.0001,min(.9999,u));v=max(.0001,min(.9999,v))
            n=np.cross(fin(u+.001,v)-fin(u-.001,v),fin(u,v+.001)-fin(u,v-.001))
            return n/max(np.linalg.norm(n),1e-8)
        for i in range(28):
            for j in range(10):
                u0,u1=i/28,(i+1)/28;v0,v1=j/10,(j+1)/10
                uv=[(u0,v0),(u1,v0),(u1,v1),(u0,v1)]
                pts=[fin(*q) for q in uv];ns=[fn(*q) for q in uv]
                col=(.18+.37*v1,.65+.16*v1,.48+.10*v1)
                for ids in ([0,1,2],[0,2,3]):m.tri(*(pts[k] for k in ids),col,normals=[ns[k] for k in ids])
        for i in range(1,18):
            u=i/19
            m.tube([fin(u,v) for v in [.06,.25,.5,.75,.95]],[.0038,.0036,.003,.002,.0008],(.34,.69,.48),5)
    # Hair hugs the whole rear scalp, then separates into broad wavy locks.
    hair=(.86,.60,.25)
    for i in range(15):
        for j in range(28):
            def scalp(ii,jj):
                a=math.pi*ii/19;b=math.tau*jj/28
                return vec((.305*math.sin(a)*math.cos(b),1.90+.365*math.cos(a),-.23+.292*math.sin(a)*math.sin(b)))
            pts=[scalp(i,j),scalp(i+1,j),scalp(i+1,j+1),scalp(i,j+1)]
            if sum(q[2] for q in pts)/4<-.31 and i>5:continue
            ns=[]
            for point in pts:
                n=(point-vec((0,1.90,-.23)))/vec((.305**2,.365**2,.292**2))
                ns.append(n/np.linalg.norm(n))
            uv=[(j/28,i/19),(j/28,(i+1)/19),((j+1)/28,(i+1)/19),((j+1)/28,i/19)]
            for ids in ([0,1,2],[0,2,3]):m.tri(*(pts[k] for k in ids),tuple(c*(1+.025*math.sin(j*3.3)) for c in hair),uv=[uv[k] for k in ids],normals=[ns[k] for k in ids])
    hr=random.Random(184)
    for lock in range(30):
        rootx=hr.uniform(-.26,.27); rooty=hr.uniform(1.77,2.15); rootz=hr.uniform(-.08,.05)
        length=hr.uniform(1.1,1.95); phase=hr.random()*math.tau
        width=hr.uniform(.17,.23) if lock<8 else (hr.uniform(.055,.11) if lock<20 else hr.uniform(.018,.045))
        centers=[]
        for j in range(18):
            t=j/17
            centers.append((rootx-t*(.50+length*.38)+math.sin(t*8+phase)*.14*t,
                            rooty-t*length*.88+math.sin(t*7+phase)*.20*t,
                            rootz+t*length*.53+math.sin(t*5+phase)*.16*t))
        shade=hr.uniform(.90,1.10)
        m.tube(centers,[(width*(1-j/17)**.65+.001,.055*(1-j/17)**.7+.001) for j in range(18)],tuple(c*shade for c in (.82,.61,.30)),10)
    return m


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for i in range(4): make_rock(100+i).save(f'rock{i}')
    column().save('column')
    arch().save('arch')
    ring_ruin().save('ring')
    kelp().save('kelp','kelp')
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
            def p(xx,zz): return (xx,-4.25+.13*math.sin(xx*.3)*math.cos(zz*.19),zz)
            ground.quad(p(x,z),p(x,z+4),p(x+4,z+4),p(x+4,z),(.19,.42,.48))
    ground.save('seabed','sand')
    surface=Mesh()
    surface.quad((-260,42,80),(260,42,80),(260,42,-300),(-260,42,-300),(.12,.64,.83))
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
    nearest=np.full((256,256),1e6); second=nearest.copy()
    for i in range(7):
        for j in range(7):
            px,py=i+rng.random(),j+rng.random()
            dx=np.abs(xx-px);dx=np.minimum(dx,7-dx)
            dy=np.abs(yy-py);dy=np.minimum(dy,7-dy)
            d=dx*dx+dy*dy
            second=np.minimum(second,np.maximum(nearest,d));nearest=np.minimum(nearest,d)
    intensity=np.exp(-(np.sqrt(second)-np.sqrt(nearest))*29)
    from PIL import ImageFilter
    stone_rng=np.random.default_rng(841)
    def periodic_noise(power,stretch=1):
        field=stone_rng.normal(size=(256,256))
        fy=np.fft.fftfreq(256)[:,None];fx=np.fft.fftfreq(256)[None,:]
        frequency=np.sqrt((fx*stretch)**2+fy**2)
        filt=np.maximum(frequency,1/256)**(-power);filt[0,0]=0
        field=np.fft.ifft2(np.fft.fft2(field)*filt).real
        low,high=np.percentile(field,[1,99])
        return np.clip((field-low)/(high-low),0,1)
    stone=periodic_noise(1.25)
    water=periodic_noise(1.7,1.4)
    Image.fromarray(np.uint8(np.clip(np.stack([intensity,stone,water],axis=-1),0,1)*255)).save(OUT/'caustics.png')

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
    place('seabed',(0,0,0))
    place('surface',(0,0,0))
    # An open, stepped archaeological basin: irregular islands, not parallel walls.
    # Every platform has foundations down to the seabed, and actors stay independent.
    terrain_rng=random.Random(391)
    def terrace(cx,cz,rx,rz,height,tiers=3):
        for tier in range(tiers):
            top=-4+(height+4)*(tier+1)/tiers
            footprint=1-.30*tier/max(tiers-1,1)
            for ix in range(-2,3):
                for iz in range(-2,3):
                    xx=ix/2;zz=iz/2
                    if xx*xx+zz*zz>1.55:continue
                    x=cx+xx*rx*footprint+terrain_rng.uniform(-.85,.85)
                    z=cz+zz*rz*footprint+terrain_rng.uniform(-.9,.9)
                    sx=rx*.31*footprint*terrain_rng.uniform(.88,1.18)
                    sz=rz*.31*footprint*terrain_rng.uniform(.88,1.18)
                    thickness=(height+4)/tiers+terrain_rng.uniform(.2,.7)
                    place(f'rock{terrain_rng.randrange(4)}',(x,top-thickness*.5-.12,z),(sx,thickness,sz),terrain_rng.uniform(-.30,.30),True)
                    if tier==tiers-1 and terrain_rng.random()<(.24 if abs(cx)>14 else .035):
                        place('kelp',(x,top+.1,z),terrain_rng.uniform(.65,1.35),terrain_rng.random()*math.tau)
                    if tier==tiers-1 and terrain_rng.random()<.30:
                        place(terrain_rng.choice(['sponge','coral_pink','coral_blue']),(x,top+.12,z),terrain_rng.uniform(.55,1.25))
    # Left foreground reaches above the camera; it ends rather than continuing as a wall.
    terrace(-18,-4,8,12,20,7)
    terrace(-21,-32,10,11,11,5)
    terrace(-30,-59,12,14,13,5)
    # Right shelf is farther away and opens onto a much wider temple plaza.
    terrace(27,-12,8,9,7,4)
    terrace(40,-42,14,13,15,5)
    terrace(46,-73,15,15,15,5)
    # Low isolated stepping platforms give a visible scale change with distance.
    terrace(4,-30,3.4,3.4,1.5,3)
    terrace(-6,-47,4.5,4.6,4,4)
    terrace(12,-60,4.5,4.8,5,4)
    terrace(28,-58,8,6,8,4)
    terrace(0,-81,7,7,9,3)
    terrace(22,-91,9,8,11,3)
    # Rubble breaks up the floor, leaving broad routes on both sides of the ruins.
    for k in range(48):
        x=R.uniform(-31,42);z=R.uniform(-112,2)
        if abs(x)<3 and z>-19:continue
        sy=R.uniform(.3,1.25)
        place(f'rock{R.randrange(4)}',(x,-4+sy*.3-.1,z),(R.uniform(.45,1.5),sy,R.uniform(.45,1.2)),R.random()*math.tau,True)
        if k%7==0:place('kelp',(x,-4+sy*.8,z),R.uniform(.7,1.4))
        if k%7==0:place('sponge',(x+.6,-4+sy*.65,z),.6)
    # Landmark hierarchy. Dominant pillar, square window, arch, elevated colonnade.
    place('column',(8,5,-38),(1.25,2.45,1.25))
    place('column',(-10,4,-33),(.95,1.75,.95))
    place('column',(-5,2,-49),(.8,1.45,.8))
    place('column',(-17,10,-59),(1.2,2.2,1.2))
    place('arch',(-1,2.2,-50),(.90,.90,.9))
    place('arch',(26,8,-53),(1.65,1.65,1.65))
    place('ring',(26,23.4,-53),(1.3,1.3,1.3))
    # Masonry supports around the window and the temple rising behind it.
    for x in [20.9,31.1]:
        for row in range(5):place('rock1',(x,9.2+row*2.7,-53),(1.1,2.8,1.0),0,True)
    for x in [37,46]:place('column',(x,17,-67),(1.55,3.4,1.55))
    place('rock0',(41.5,45.5,-67),(6.5,1.1,2))
    place('column',(43,12,-81),(1.25,2.8,1.25))
    place('arch',(-15,5,-91),(1.25,1.25,1.25))
    place('column',(-4,0,-99),(.8,1.55,.8))
    place('column',(8,5,-114),(1.1,2.1,1.1))
    place('arch',(14,3,-118),(1.1,1.1,1.1))
    # Foreground plants frame the view without forming a wall of broad leaves.
    for p,scale in [((-8,1,5),1.3),((-7.8,4,-7),1.5),((-11,11,-5),1.3),((13,3,-5),1.6),((18,7,-19),1.5),((7,-4,-11),.9),((-4,-4,-22),1.3),((14,-4,-36),1.4)]:
        place('kelp',p,scale,R.random()*math.tau)
    # Sun shafts are integrated through water in the depth-aware post process.
    # Preserve RNG stream so this renderer change does not reshuffle the fish.
    for _ in range(8):R.uniform(1.2,2)
    # Shared fish geometry/material => one instanced batch per visible mesh.
    for school in range(5):
        cx,cy,cz=[(-8,6,-6),(0,13,-35),(20,7,-25),(-10,4,-3),(22,16,-67)][school]
        for k in range(50 if school in [1,4] else 10):
            place('fish_blue' if school in [1,4] else 'fish',(cx+R.gauss(0,2.2),cy+R.gauss(0,.7),cz+R.gauss(0,1.5)),R.uniform(.45,.8) if school in [1,4] else R.uniform(.8,1.4),.1*school)
    place('ray',(-7,19,-30),1.8,-.5)
    place('ray',(1,19,-55),1.25,.3)
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
