"""Deterministic, editable geometry source. Emit shared glTF meshes and world layout.

Coordinates: meters, Y up, swimming forward -Z. Seed 73. No external assets.
Regenerate with python3 tools/build_assets.py. GLBs can be edited in Blender.
"""
import json
import hashlib
import shutil
import subprocess
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
        # Index the complete vertex tuple. Preserve hard normals, UV seams, colors
        # and every triangle exactly; avoid re-running VS for duplicate corners.
        packed=np.concatenate([np.asarray(v,dtype='<f4') for v in [self.p,self.n,self.c,self.uv]],axis=1)
        unique,indices=np.unique(packed,axis=0,return_inverse=True)
        assert np.array_equal(unique[indices],packed), 'Indexed mesh changed a vertex attribute'
        for values, kind in [(unique[:,:3],"VEC3"),(unique[:,3:6],"VEC3"),(unique[:,6:10],"VEC4"),(unique[:,10:],"VEC2")]:
            a = np.asarray(values, dtype="<f4")
            view = {"buffer":0,"byteOffset":len(binary),"byteLength":a.nbytes,"target":34962}
            binary.extend(a.tobytes())
            views.append(view)
            accessor = {"bufferView":len(views)-1,"componentType":5126,"count":len(a),"type":kind}
            if len(accessors)==0:
                accessor.update(min=a.min(axis=0).tolist(),max=a.max(axis=0).tolist())
            accessors.append(accessor)
        index_data=indices.astype('<u4')
        views.append({"buffer":0,"byteOffset":len(binary),"byteLength":index_data.nbytes,"target":34963})
        binary.extend(index_data.tobytes())
        accessors.append({"bufferView":len(views)-1,"componentType":5125,"count":len(index_data),"type":"SCALAR"})
        doc={"asset":{"version":"2.0","generator":"Mermaid deterministic asset source"},
             "scene":0,"scenes":[{"nodes":[0]}],"nodes":[{"mesh":0,"name":name}],
             "meshes":[{"name":name,"primitives":[{"attributes":{"POSITION":0,"NORMAL":1,"COLOR_0":2,"TEXCOORD_0":3},"indices":4,"material":0}]}],
             "materials":[{"name":"reef","pbrMetallicRoughness":{"baseColorFactor":[1,1,1,1],"metallicFactor":0,"roughnessFactor":.8}}],
             "buffers":[{"byteLength":len(binary)}],"bufferViews":views,"accessors":accessors}
        encoded=json.dumps(doc,separators=(',',':')).encode()
        encoded += b' ' * (-len(encoded)%4)
        payload=struct.pack('<II',len(encoded),0x4e4f534a)+encoded+struct.pack('<II',len(binary),0x004e4942)+binary
        (OUT/f'{name}.glb').write_bytes(struct.pack('<III',0x46546c67,2,12+len(payload))+payload)
        sampler='scene_texture' if category=='blit' else 'caustics'
        pattern_texture = 'surface_water.png' if category == 'surface' else 'caustics.png'
        texture=f' textures {{ sampler: "{sampler}" texture: "/assets/generated/{pattern_texture}" }}\n'
        if category!='blit':texture+=' textures { sampler: "stone_detail" texture: "/assets/textures/limestone-v1.png" }\n'
        (OUT/f'{name}.model').write_text(f'mesh: "/assets/generated/{name}.glb"\nmaterials {{\n name: "reef"\n material: "/render/{category}.material"\n{texture}}}\n')
        # Visual offset keeps the physical swimming/camera anchor unchanged.
        model_offset = 'x:.20 y:-.22 z:0' if name == 'mermaid' else 'x:0 y:0 z:0'
        (OUT/f'{name}.go').write_text(f'components {{ id: "model" component: "/assets/generated/{name}.model" position {{ {model_offset} }} rotation {{x:0 y:0 z:0 w:1}} }}\n')
        STATS[name]={"triangles":len(self.p)//3,"vertices":len(unique),"unindexed_vertices":len(self.p),"bytes":12+len(payload)}


def make_rock(seed):
    """Convex fractured stone: skewed broad faces and independently cut corners."""
    rng=random.Random(seed);m=Mesh()
    points=[vec((x,y,z)) for x in [-1.15,1.15] for y in [-.72,.72] for z in [-1.15,1.15]]
    faces=[[points[i] for i in ids] for ids in [(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]]
    def clip(normal,distance):
        nonlocal faces
        n=vec(normal);length=np.linalg.norm(n);n/=length;d=distance/length
        result=[];edge=[]
        for face in faces:
            polygon=[]
            for i,a in enumerate(face):
                b=face[(i+1)%len(face)];da=np.dot(a,n)-d;db=np.dot(b,n)-d
                if da<=1e-8:polygon.append(a)
                if (da<0 and db>0) or (da>0 and db<0):
                    cut=a+(b-a)*da/(da-db);polygon.append(cut);edge.append(cut)
            if len(polygon)>=3:result.append(polygon)
        unique=[]
        for v in edge:
            if not any(np.linalg.norm(v-u)<1e-6 for u in unique):unique.append(v)
        if len(unique)>=3:
            center=sum(unique)/len(unique);axis=np.cross(n,vec((0,1,0)))
            if np.linalg.norm(axis)<.01:axis=np.cross(n,vec((1,0,0)))
            axis/=np.linalg.norm(axis);other=np.cross(n,axis)
            unique.sort(key=lambda v:math.atan2(np.dot(v-center,other),np.dot(v-center,axis)))
            result.append(unique)
        faces=result
    for sign in [-1,1]:
        clip((sign,rng.uniform(-.1,.1),rng.uniform(-.15,.15)),rng.uniform(.94,1.08))
        clip((rng.uniform(-.13,.13),rng.uniform(-.1,.1),sign),rng.uniform(.91,1.08))
        clip((rng.uniform(-.16,.16),sign,rng.uniform(-.14,.14)),rng.uniform(.44,.55))
    for sx in [-1,1]:
        for sz in [-1,1]:
            clip((sx,rng.uniform(-.2,.2),sz),rng.uniform(1.50,1.75))
            for sy in [-1,1]:clip((sx,sy*rng.uniform(1.1,1.7),sz),rng.uniform(1.95,2.40))
    for face in faces:
        center=sum(face)/len(face)
        n=np.cross(face[1]-face[0],face[2]-face[0]);n/=max(np.linalg.norm(n),1e-8)
        if np.dot(n,center)<0:face.reverse();n=-n
        weather=rng.uniform(.92,1.07)
        col=vec((.23,.32,.36))*(1+max(n[1],0)*.10)*weather
        for j in range(1,len(face)-1):m.tri(face[0],face[j],face[j+1],col)
    return m


def column():
    m=Mesh()
    stone=(.32,.38,.37)
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
    col=(.32,.38,.37)
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
    m=Mesh(); col=(.34,.40,.39)
    for j in range(28):
        a,b=j*math.tau/28+.004,(j+1)*math.tau/28-.004
        pts=[]
        for z in [-.6,.6]:
            for t,r in [(a,3.05),(a,None),(b,None),(b,3.05)]:
                r=r or ((4.35+.20*math.sin(j*2.7)) if math.sin(t)>0 else 4.35/max(abs(math.cos(t)),abs(math.sin(t))))
                pts.append((r*math.cos(t),r*math.sin(t),z))
        for ids in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:
            m.quad(*(pts[k] for k in ids),tuple(v*(.95+.05*math.sin(j*2.1)) for v in col))
    # Broken crown stones and shallow coping provide real depth and cast shadows.
    for x,y,z,sx,sy,sz in [(-2.6,3.5,-.05,1.25,.7,1.5),(-.9,4.35,.05,1.1,.8,1.5),
                            (1.7,3.95,-.08,1.25,.55,1.4),(3.85,1.3,.10,.8,1.0,1.5)]:
        m.box((x,y,z),(sx,sy,sz),(.29,.41,.43),.12)
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
            col=(.25+rng.random()*.025,.37+rng.random()*.08,.08)
            for j in range(7):
                t0,t1=j/7,(j+1)/7
                m.quad(point(t0,-1),point(t0,1),point(t1,1),point(t1,-1),col)
    return m


def coral(color,sponges=False):
    m=Mesh(); rng=random.Random(129 if sponges else 817)
    if sponges:
        for branch in range(7):
            x,z=rng.uniform(-.7,.7),rng.uniform(-.45,.45)
            h=rng.uniform(.50,1.5);r=rng.uniform(.13,.21)
            bend=rng.uniform(-.12,.12)
            levels=[(0,r*1.08),(h*.12,r*.85),(h*.55,r*.91),(h*.92,r*1.12),(h,r*1.13),(h+.015,r*.92),(h-.06,r*.72),(h*.18,r*.50)]
            rings=[]
            for yy,rr in levels:
                ring=[]
                for j in range(16):
                    a=j*math.tau/16
                    wobble=.018*math.sin(a*3+branch)*yy/h
                    ring.append((x+bend*(yy/h)**2+rr*math.cos(a),yy+wobble,z+.06*(yy/h)**2+rr*math.sin(a)))
                rings.append(ring)
            for i in range(len(rings)-1):
                shade=1.10 if i in [3,4] else (.30 if i>5 else 1)
                for j in range(16):
                    jj=(j+1)%16
                    m.quad(rings[i][j],rings[i+1][j],rings[i+1][jj],rings[i][jj],tuple(v*shade for v in color))
    else:
        def branch(base,direction,length,radius,depth,phase):
            direction=vec(direction);direction/=np.linalg.norm(direction)
            centers=[]
            for j in range(6):
                t=j/5
                centers.append(vec(base)+direction*length*t+vec((math.sin(t*2+phase),0,math.cos(t*2+phase)))*length*.13*t)
            m.tube(centers,[radius*(1-j/6)*.9+.006 for j in range(6)],color,5)
            m.ellipsoid(centers[-1],(.012,.015,.012),color,3,6)
            if depth:
                for side in [-1,1]:
                    d=direction+vec((side*rng.uniform(.45,.85),.15,rng.uniform(-.35,.35)))
                    branch(centers[rng.choice([3,4])],d,length*rng.uniform(.48,.72),radius*.62,depth-1,phase+side)
        for i in range(6):
            branch((rng.uniform(-.55,.55),0,rng.uniform(-.35,.35)),(rng.uniform(-.3,.3),1,rng.uniform(-.2,.2)),rng.uniform(.65,1.1),rng.uniform(.035,.055),2,i*1.7)
    return m


def ribbon_kelp():
    m=Mesh(); rng=random.Random(546)
    for leaf in range(5):
        height=rng.uniform(3.7,7); spread=rng.uniform(-1,1);phase=rng.random()*math.tau
        def point(t,u):
            width=math.sin(math.pi*t)**.75*rng_width
            center=vec((spread*t+math.sin(t*4+phase)*.30*t,height*t,.20*math.sin(t*6+phase)*t))
            return center+vec((u*width,.025*math.sin(u*math.pi),u*width*.6+.06*math.sin(t*18+phase)*u))
        rng_width=rng.uniform(.16,.33)
        color=(rng.uniform(.16,.24),rng.uniform(.31,.40),.07)
        for j in range(20):
            for k in range(3):
                t0,t1=j/20,(j+1)/20;u0,u1=-1+k*2/3,-1+(k+1)*2/3
                m.quad(point(t0,u0),point(t0,u1),point(t1,u1),point(t1,u0),color)
    return m


def fish():
    m=Mesh(); gold=(.94,.76,.12)
    m.ellipsoid((0,0,0),(.31,.16,.095),gold,6,12)
    m.tri((-.26,0,0),(-.49,.17,0),(-.49,-.17,0),(.98,.76,.17))
    m.tri((0,.12,0),(-.17,.27,0),(-.19,.08,0),(.78,.51,.04))
    m.ellipsoid((.20,.04,.083),(.024,.024,.016),(.025,.035,.045),3,5)
    m.ellipsoid((.20,.04,-.083),(.024,.024,.016),(.025,.035,.045),3,5)
    m.uv=[(max(-p[0],0),0) for p in m.p]
    return m


def ray():
    m=Mesh();top=(.18,.35,.40);belly=(.66,.68,.49)
    m.ellipsoid((0,0,-.06),(.25,.095,.49),top,10,16)
    for k in range(0,len(m.p),3):
        if sum(p[1] for p in m.p[k:k+3])<0:
            for j in range(k,k+3):m.c[j]=(*belly,1)
    for side in [-1,1]:
        def wing(u,v,layer):
            front=-.38*(1-u)+.18*u;back=.42*(1-u)+.18*u
            return (side*(.10+u*1.45),.03+.17*u**3-.06*math.sin(v*math.pi)*(1-u)+layer*.018*(1-u),front+(back-front)*v)
        for i in range(12):
            for j in range(8):
                u0,u1=i/12,(i+1)/12;v0,v1=j/8,(j+1)/8
                for layer,col in [(1,top),(-1,belly)]:
                    pts=[wing(u0,v0,layer),wing(u1,v0,layer),wing(u1,v1,layer),wing(u0,v1,layer)]
                    if layer<0:pts.reverse()
                    m.quad(*pts,col)
        m.tube([(side*.14,-.015,-.39),(side*.20,-.02,-.52),(side*.28,.015,-.57)],[.045,.045,.025],belly,8)
        m.ellipsoid((side*.19,.065,-.28),(.03,.018,.028),(.035,.07,.08),5,8)
    m.tube([(0,0,.30),(0,-.03,.8),(0,-.10,1.4),(0,-.12,1.85)],[.04,.022,.010,.002],top,7)
    return m


def mermaid():
    m=Mesh(); skin=(.93,.70,.47,0.0)
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
        elbow=(side*.86,.77,-.18 if side<0 else -.28)
        wrist=(side*1.36,.35,-.28 if side<0 else -.53)
        m.tube([(side*.39,1.19,-.22),(side*.52,1.04,-.20),elbow,(side*1.1,.55,wrist[2]+.05),wrist],
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
    centers=[(0,.14,.065),(.025,-.13,.16),(.015,-.43,.32),(-.06,-.72,.52),(-.15,-1.00,.72),(-.24,-1.24,.91),(-.27,-1.45,1.07),(-.21,-1.61,1.18)]
    radii=[(.355,.25),(.405,.275),(.385,.265),(.315,.225),(.245,.18),(.165,.125),(.10,.08),(.07,.055)]
    m.tube(centers,radii,(.045,.57,.52,.25),40)
    # Two swept, pointed lobes. Curved outlines replace straight triangular fans.
    def bez(points,t):
        a,b,c,d=[vec(p) for p in points]
        return (1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d
    for side in [-1,1]:
        def fin(u,v):
            if u<.55:
                edge=bez([(0,-.47,.54),(.20,-.82,.59),(.55,-.70,.20),(.88,-1.08,-.04)],u/.55)
            else:
                edge=bez([(.88,-1.08,-.04),(.84,-.66,-.10),(.43,-.08,-.045),(0,0,0)],(u-.55)/.45)
            offset=vec((side*edge[0]*(1.35 if side<0 else 1.0),edge[1]*(1.60 if side<0 else 1.08),edge[2]+side*edge[0]*.15))
            angle=-.25
            offset[0],offset[1]=math.cos(angle)*offset[0]-math.sin(angle)*offset[1],math.sin(angle)*offset[0]+math.cos(angle)*offset[1]
            q=vec((-.21,-1.59,1.18))+offset*v
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
                col=(.24+.39*v1,.56+.16*v1,.39+.15*v1,.5)
                for ids in ([0,1,2],[0,2,3]):m.tri(*(pts[k] for k in ids),col,normals=[ns[k] for k in ids])
        for i in range(1,18):
            u=i/19
            m.tube([fin(u,v) for v in [.06,.25,.5,.75,.95]],[.0038,.0036,.003,.002,.0008],(.34,.69,.48,.5),5)
    # Hair hugs the whole rear scalp, then separates into broad wavy locks.
    hair=(.84,.66,.36)
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
            for ids in ([0,1,2],[0,2,3]):m.tri(*(pts[k] for k in ids),(*tuple(c*(1+.025*math.sin(j*3.3)) for c in hair),.75),uv=[uv[k] for k in ids],normals=[ns[k] for k in ids])
    hr=random.Random(184)
    for lock in range(30):
        rootx=hr.uniform(-.26,.27); rooty=hr.uniform(1.77,2.15); rootz=hr.uniform(-.08,.05)
        length=hr.uniform(1.1,1.95); phase=hr.random()*math.tau
        width=hr.uniform(.17,.23) if lock<8 else (hr.uniform(.055,.11) if lock<20 else hr.uniform(.018,.045))
        centers=[]
        for j in range(18):
            t=j/17
            centers.append((rootx-math.sin(t*math.pi/2)*(.50+length*.42)+math.sin(t*10+phase)*.20*math.sin(t*math.pi),
                            rooty-t**1.12*length*.88+math.sin(t*8+phase)*.20*t,
                            rootz+(1-math.cos(t*math.pi/2))*length*.57+math.sin(t*7+phase)*.18*t))
        shade=hr.uniform(.90,1.10)
        m.tube(centers,[(width*(.6+.6*math.sin(math.pi*j/17))*(1-j/17)**.50+.001,.055*(1-j/17)**.7+.001) for j in range(18)],(*tuple(c*shade for c in (.84,.66,.37)),.75),10)
    # Match upper-body proportions without changing the controller/hips position.
    for i,p in enumerate(m.p):
        if p[1]>1.4:
            p[1]-=.22
        elif p[1]>.3:
            p[1]=.3+(p[1]-.3)*.8
            n=m.n[i].copy();n[1]/=.8;m.n[i]=n/np.linalg.norm(n)
    return m


def finish_character():
    """Cache the Blender-authored continuous skin, preserving other mesh parts."""
    source=ROOT/'assets/source';source.mkdir(exist_ok=True)
    raw=source/'mermaid-procedural.glb';finished=source/'mermaid-finished.glb'
    script=ROOT/'tools/finish_character.py';cache=source/'mermaid-build.json'
    data=(OUT/'mermaid.glb').read_bytes()
    signature=hashlib.sha256(data+script.read_bytes()).hexdigest()
    cached=json.loads(cache.read_text()) if cache.exists() else {}
    if cached.get('signature')!=signature or not finished.exists():
        raw.write_bytes(data)
        blender=shutil.which('blender') or '/snap/bin/blender'
        subprocess.run([blender,'--background','--python',str(script),'--',str(raw),str(finished),str(source/'mermaid.blend')],check=True)
        cache.write_text(json.dumps({'signature':signature,'method':'voxel union .018, smooth3, decimate .55; preserve other parts'},indent=2)+'\n')
    shutil.copyfile(finished,OUT/'mermaid.glb')
    data=finished.read_bytes();n=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+n])
    triangles=sum(doc['accessors'][p['indices']]['count']//3 if 'indices' in p else doc['accessors'][p['attributes']['POSITION']]['count']//3 for mesh in doc['meshes'] for p in mesh['primitives'])
    STATS['mermaid']={'triangles':triangles,'bytes':len(data),'source':'assets/source/mermaid.blend'}



def finish_ruins():
    """Preserve editable Blender sources and cache finished shared architectural meshes."""
    source=ROOT/'assets/source';source.mkdir(exist_ok=True)
    names=['column','arch','ring'];script=ROOT/'tools/finish_ruins.py';cache=source/'ruins-build.json'
    raw={name:(OUT/f'{name}.glb').read_bytes() for name in names}
    signature=hashlib.sha256(b''.join(raw.values())+script.read_bytes()).hexdigest()
    cached=json.loads(cache.read_text()) if cache.exists() else {}
    if cached.get('signature')!=signature or not all((source/f'{name}-finished.glb').exists() for name in names):
        for name,data in raw.items():(source/f'{name}-procedural.glb').write_bytes(data)
        subprocess.run([shutil.which('blender') or '/snap/bin/blender','--background','--python',str(script),'--',str(source)],check=True)
        cache.write_text(json.dumps({'signature':signature,'method':'physical erosion .024; bevel .045 two segments; weighted normals'},indent=2)+'\n')
    for name in names:
        finished=source/f'{name}-finished.glb';shutil.copyfile(finished,OUT/f'{name}.glb')
        data=finished.read_bytes();n=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+n])
        triangles=sum(doc['accessors'][p['indices']]['count']//3 if 'indices' in p else doc['accessors'][p['attributes']['POSITION']]['count']//3 for mesh in doc['meshes'] for p in mesh['primitives'])
        STATS[name]={'triangles':triangles,'bytes':len(data),'source':'assets/source/ruins.blend'}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for i in range(4): make_rock(100+i).save(f'rock{i}')
    for name,mesh,part_id in [('column',column(),.1),('arch',arch(),.2),('ring',ring_ruin(),.3)]:
        # Debug semantic ID only. Normal output stays opaque; no lighting baked in.
        mesh.c=[(*c[:3],part_id) for c in mesh.c]
        mesh.save(name)
    kelp().save('kelp','kelp')
    ribbon_kelp().save('ribbon_kelp','kelp')
    coral((.54,.28,.57),True).save('sponge','stone')
    coral((.84,.39,.41)).save('coral_pink','stone')
    coral((.28,.39,.72)).save('coral_blue','stone')
    coral((.72,.61,.24)).save('coral_gold','stone')
    fish().save('fish','fish')
    bluefish=fish()
    bluefish.c=[(.10,.28,.36,1) if c[0]>.1 else c for c in bluefish.c]
    bluefish.save('fish_blue','fish')
    orange=fish();orange.c=[(.73,.38,.14,1) if c[0]>.1 else c for c in orange.c];orange.save('fish_orange','fish')
    silver=fish();silver.c=[(.65,.73,.63,1) if c[0]>.1 else c for c in silver.c];silver.save('fish_silver','fish')
    ray().save('ray','ray')
    mermaid().save('mermaid','mermaid')
    ground=Mesh()
    for z in range(-125,21,4):
        for x in range(-60,61,4):
            def p(xx,zz): return (xx,-4.25+.13*math.sin(xx*.3)*math.cos(zz*.19),zz)
            ground.quad(p(x,z),p(x,z+4),p(x+4,z+4),p(x+4,z),(.19,.42,.48))
    ground.save('seabed','sand')
    surface=Mesh()
    surface.quad((-1000,50,200),(1000,50,200),(1000,50,-1000),(-1000,50,-1000),(.12,.64,.83))
    surface.save('surface','surface')
    particle=Mesh()
    particle.ellipsoid((0,0,0),(.025,.025,.025),(.38,.74,.80),3,4)
    particle.save('particle','dust')
    fullscreen=Mesh()
    fullscreen.quad((-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0),(1,1,1))
    fullscreen.save('fullscreen','blit')

    # Receiver pattern only: curve cell boundaries by a seamless wave field.
    # Preserve the old intensity distribution and the surface's entire texture,
    # so this fitting pass does not retune brightness or change water appearance.
    rng=np.random.default_rng(73)
    yy,xx=np.mgrid[0:256,0:256]/256*7
    sites=[(i+rng.random(),j+rng.random()) for i in range(7) for j in range(7)]
    def receiver_pattern(x,y):
        nearest=np.full((256,256),1e6);second=nearest.copy()
        for px,py in sites:
            dx=np.abs(x-px);dx=np.minimum(dx,7-dx)
            dy=np.abs(y-py);dy=np.minimum(dy,7-dy)
            d=dx*dx+dy*dy
            second=np.minimum(second,np.maximum(nearest,d));nearest=np.minimum(nearest,d)
        return np.exp(-(np.sqrt(second)-np.sqrt(nearest))*29)
    surface_pattern=receiver_pattern(xx,yy)
    u,v=xx/7,yy/7
    wave_x=.38*np.sin(math.tau*(2*u+v)+.8)+.18*np.sin(math.tau*(3*v-u)+1.6)
    wave_y=.34*np.sin(math.tau*(u-2*v)-.6)+.14*np.sin(math.tau*(3*u+v)+2.3)
    curved=receiver_pattern((xx+wave_x)%7,(yy+wave_y)%7)
    intensity=np.empty_like(curved)
    intensity.ravel()[np.argsort(curved.ravel())]=np.sort(surface_pattern.ravel())
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
    field=stone_rng.normal(size=(256,256))
    fy=np.fft.fftfreq(256)[:,None];fx=np.fft.fftfreq(256)[None,:]
    frequency=np.sqrt((fx*1.6)**2+fy**2)
    band=np.exp(-(frequency/.028)**2)*(1-np.exp(-(frequency/.006)**2))
    water=np.fft.ifft2(np.fft.fft2(field)*band).real
    low,high=np.percentile(water,[1,99]);water=np.clip((water-low)/(high-low),0,1)
    Image.fromarray(np.uint8(np.clip(np.stack([intensity,stone,water],axis=-1),0,1)*255)).save(OUT/'caustics.png')
    Image.fromarray(np.uint8(np.clip(np.stack([surface_pattern,stone,water],axis=-1),0,1)*255)).save(OUT/'surface_water.png')

    objects=[]; obstacles=[]
    placements=0
    def place(asset,p,scale=(1,1,1),yaw=0,collision=False,pitch=0,roll=0,label=None):
        nonlocal placements
        name=label or f'{asset}_{placements:04d}'
        placements+=1
        if isinstance(scale,(int,float)):scale=(scale,)*3
        def multiply(a,b):
            ax,ay,az,aw=a;bx,by,bz,bw=b
            return (aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw,aw*bw-ax*bx-ay*by-az*bz)
        q=multiply(multiply((0,math.sin(yaw/2),0,math.cos(yaw/2)),(math.sin(pitch/2),0,0,math.cos(pitch/2))),(0,0,math.sin(roll/2),math.cos(roll/2)))
        objects.append(f'instances {{ id: "{name}" prototype: "/assets/generated/{asset}.go" position {{x:{p[0]} y:{p[1]} z:{p[2]}}} rotation {{x:{q[0]} y:{q[1]} z:{q[2]} w:{q[3]}}} scale3 {{x:{scale[0]} y:{scale[1]} z:{scale[2]}}} }}')
        if collision:
            qx,qy,qz,qw=q
            rotation=np.array([[1-2*(qy*qy+qz*qz),2*(qx*qy-qz*qw),2*(qx*qz+qy*qw)],[2*(qx*qy+qz*qw),1-2*(qx*qx+qz*qz),2*(qy*qz-qx*qw)],[2*(qx*qz-qy*qw),2*(qy*qz+qx*qw),1-2*(qx*qx+qy*qy)]])
            extent=abs(rotation)@vec((scale[0]*.88,scale[1]*.48,scale[2]*.88))
            obstacles.append([round(float(v),3) for v in [*p,*extent]])
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
                    if tier<tiers-1 and abs(ix)<2 and abs(iz)<2:continue
                    x=cx+xx*rx*footprint+terrain_rng.uniform(-.85,.85)
                    z=cz+zz*rz*footprint+terrain_rng.uniform(-.9,.9)
                    sx=rx*.31*footprint*terrain_rng.uniform(.88,1.18)
                    sz=rz*.31*footprint*terrain_rng.uniform(.88,1.18)
                    thickness=(height+4)/tiers+terrain_rng.uniform(.2,.7)
                    cell_top=top+terrain_rng.uniform(-.40,.40)
                    place(f'rock{terrain_rng.randrange(4)}',(x,cell_top-thickness*.5-.12,z),(sx,thickness,sz),terrain_rng.uniform(-.30,.30),True,pitch=terrain_rng.uniform(-.09,.09),roll=terrain_rng.uniform(-.07,.07))
                    if tier==tiers-1 and terrain_rng.random()<(.24 if abs(cx)>14 else .035):
                        place('kelp',(x,cell_top+.1,z),terrain_rng.uniform(.65,1.35),terrain_rng.random()*math.tau)
                    if tier==tiers-1 and terrain_rng.random()<.30:
                        place(terrain_rng.choice(['sponge','coral_pink','coral_blue']),(x,cell_top+.12,z),terrain_rng.uniform(.55,1.25))
    # Left foreground reaches above the camera; it ends rather than continuing as a wall.
    terrace(-20,-12,6.7,9,14,7)
    terrace(-22,-37,9,10,8,5)
    terrace(-30,-59,12,14,13,5)
    # Right shelf is farther away and opens onto a much wider temple plaza.
    terrace(27,-12,8,9,7,4)
    terrace(40,-42,14,13,15,5)
    terrace(46,-73,15,15,15,5)
    # Low isolated stepping platforms give a visible scale change with distance.
    terrace(3.0,-42,3.0,3.2,-.2,2)
    terrace(-7,-43,5.0,4.5,5,4)
    terrace(12,-60,4.5,4.8,5,4)
    terrace(28,-58,8,6,2,3)
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
    # Opening camera basis, matching main.script. Fixed world assets, no billboarding.
    camera=vec((-.4,6.519904,12.992801));look=vec((-.35,5.260171,-12))
    forward=look-camera;forward/=np.linalg.norm(forward)
    right=np.cross(forward,vec((0,1,0)));right/=np.linalg.norm(right)
    upward=np.cross(right,forward);f=1/math.tan(math.radians(59)/2)
    def at(u,v,depth):
        return camera+forward*depth+right*((u-.5)*2*(16/9)*depth/f)+upward*((.5-v)*2*depth/f)
    landmark_records=[]
    def landmark(asset,u,v,depth,scale,label=None):
        p=at(u,v,depth)
        place(asset,p,scale,label=label)
        if label:
            landmark_records.append({'id':label,'asset':asset,'reference_anchor_uv':[u,v],
                                     'world_position':[float(x) for x in p],'scale':list(scale),'depth_m':depth})
        return p
    # Broken intermediate shelves occupy the basin rather than a broad bare floor.
    for u,v,d,rx,rz,tiers in [(.29,.55,35,4.5,4.0,4),(.37,.59,29,3.1,3.5,4),
                              (.50,.76,25,2.0,2.5,3),(.57,.68,41,2.7,3.1,4),
                              (.64,.61,51,3.0,3.4,4)]:
        p=at(u,v,d)
        terrace(float(p[0]),float(p[2]),rx,rz,float(p[1]),tiers)
    # Pillar base/cap, circular opening and gateway have distinct reference proportions.
    pillar=at(.582,.43,51)
    terrace(float(pillar[0]),float(pillar[2]),3.8,4.0,float(pillar[1])-.1,5)
    landmark('column',.582,.43,51,(1.15,1.88,1.15),'main_pillar')
    landmark('column',.423,.48,49,(.85,1.25,.85),'left_front_pillar')
    landmark('column',.447,.49,63,(.7,1.40,.7),'left_rear_pillar')
    # Required faint structures are actual stone meshes even when blue haze
    # makes their RGB difference small. Never count blue background as a column.
    for label,u,v,d,scale in [
        ('left_distant_pillar',.347,.48,69,(.65,1.12,.65)),
        ('left_distant_pillar_pair',.375,.48,76,(.6,1.35,.6)),
        ('central_distant_pillar',.465,.51,82,(.4,1.0,.4)),
        ('pillar_behind_main',.624,.44,61,(.82,1.50,.82)),
        ('ring_left_pillar',.646,.43,64,(.85,2.14,.85)),
        ('right_rear_pillar',.855,.36,91,(1.2,3.1,1.2)),
    ]:
        p=landmark('column',u,v,d,scale,label)
        if label not in ['ring_left_pillar','right_rear_pillar']:
            height=max(.2,float(p[1])+4.25)
            place('rock1',(p[0],-4.25+height*.5,p[2]),(1.25,height,1.25),0,True)

    gateway=at(.536,.555,58)
    terrace(float(gateway[0]),float(gateway[2]),3.4,2.8,float(gateway[1])-.1,3)
    landmark('arch',.536,.555,58,(.83,.90,.83),'central_gateway')
    landmark('arch',.701,.515,66,(1.55,1.55,1.55),'ring_gateway')
    landmark('ring',.701,.245,66,(1.5,1.5,1.5),'circular_window')
    # Square wall supports continue down to the temple shelf, leaving the arch open.
    ring=at(.701,.245,66)
    for side in [-1,1]:
        for row in range(5):place('rock1',(ring[0]+side*6.2,7.6+row*2.6,ring[2]),(1.15,2.7,1.1),0,True)
    for x in [34,46]:place('column',(x,15,-67),(1.55,3.65,1.55))
    place('rock0',(40,45.5,-67),(10.5,1.1,2))
    place('column',(43,12,-81),(1.25,2.8,1.25))
    place('arch',(-15,5,-91),(1.25,1.25,1.25))
    place('column',(-4,0,-99),(.8,1.55,.8))
    place('column',(8,5,-114),(1.1,2.1,1.1))
    place('arch',(14,3,-118),(1.1,1.1,1.1))
    # Foreground plants frame the view without forming a wall of broad leaves.
    for p,scale in [((-8,1,5),1.3),((-7.8,4,-7),1.5),((-11,11,-5),1.3),((13,3,-5),1.6),((18,7,-19),1.5),((-4,-4,-22),1.3),((14,-4,-36),1.4)]:
        place('kelp',p,scale,R.random()*math.tau)
    # Reference-specific foreground shelves, coral and plants. Fixed 3D positions.
    for asset,p,scale,yaw in [
        ('rock1',(-8.5,.15,-1),(3.0,2.4,2.6),.12),
        ('rock2',(-7.0,-1.4,1),(2.6,2.1,2.2),-.16),
        ('rock3',(-7.5,4.2,-9),(3.7,2.1,3.1),.18),
        ('rock2',(-7.5,-.3,-9),(3.5,6.8,3.0),.1),
        ('rock0',(11,-3.0,-1),(3.5,3.8,3.4),-.18),
        ('rock2',(15,1.2,-7),(4.0,3.7,3.6),.22),
        ('rock1',(7.4,-1.4,-19),(2.8,4.5,2.8),.18),
        ('rock3',(-2.4,-2.1,-17),(1.7,2.4,1.8),-.2),
    ]:place(asset,p,scale,yaw,True)
    for asset,p,scale in [
        ('sponge',(-9.5,2.1,-2),1.0),('coral_pink',(-7.5,1.5,-1.5),1.2),
        ('coral_blue',(-7,4.5,-9),.95),('sponge',(-11,4.5,-11),1.1),
        ('coral_pink',(-9,9,-20),1.1),('sponge',(-15.5,14.42,-14),.9),
        ('sponge',(13,-1.6,-1.5),2.2),('coral_pink',(14.4,3.1,-7),1.4),
        ('coral_blue',(12,3,-9),1.2),('sponge',(7.8,.9,-19),1.1),
        ('coral_pink',(-2.5,-.9,-17),.8),('sponge',(2.0,-3.7,-14),.9),
    ]:place(asset,p,scale,R.random()*math.tau)
    for p,scale in [((-8,1.5,-1),.95),((-7,4.5,-8),1.2),((10,1,-3),1.3),((7.6,.9,-19),1.0),((-4.5,-1.8,-12),1.1)]:
        place('kelp',p,scale,R.random()*math.tau)
    for u,v,depth,scale in [(-.08,1.02,14,(2.8,1.35,1.4)),(.18,.85,22,1.45),(.26,.54,40,1.5),(.35,.61,46,1.5),(.72,1.02,16,.75),(.86,.60,45,1.6)]:
        place('ribbon_kelp',at(u,v,depth),scale,R.random()*.5)
    # Reference kelp has irregular clusters of narrow fronds at different depths.
    planting_rng=random.Random(1582)
    for u,v,h,d in [(.16,.69,.34,22),(.24,.54,.23,38),(.28,.54,.35,40),
                    (.35,.57,.21,48),(.40,.49,.20,60),(.79,.67,.30,40),
                    (.86,.44,.36,55),(.95,.49,.36,42),(.98,.75,.40,22),
                    (.18,.98,.28,16),(.71,.98,.21,17)]:
        for j in range(2):
            p=at(u+planting_rng.uniform(-.008,.008),v,d+planting_rng.uniform(-.7,.7))
            size=h*d*2/(f*5.5)*planting_rng.uniform(.80,1.12)
            place('kelp',p,(size*.70,size,size*.70),planting_rng.random()*math.tau)
    place('coral_gold',(-8.5,2.0,-2),1.2)
    edge=at(.025,.58,12)
    place('rock0',(edge[0],edge[1]-.5,edge[2]),(2.2,.9,1.4),.1,True)
    place('sponge',edge,1.4)
    # Sun shafts are integrated through water in the depth-aware post process.
    # Preserve RNG stream so this renderer change does not reshuffle the fish.
    for _ in range(8):R.uniform(1.2,2)
    # Independent shared-mesh actors, arranged in layers of depth.
    for u,v,d,scale in [(.055,.46,9,1.2),(.13,.48,11,1.0),(.15,.43,12,.8),(.07,.53,10,.9),(.035,.57,9,.8),(.18,.54,12,.7),(.10,.50,10,.9)]:
        p=at(u,v,d);p[0]-=math.sin(.54+p[2]*.12)*1.1
        p[1]-=math.sin(2.4+p[2])*.12
        place('fish',p,scale,math.pi)
    for asset,uv,depth,count,spread in [
        ('fish_blue',(.47,.35),52,75,(4.2,1.1,2.6)),
        ('fish_orange',(.84,.60),28,35,(1.5,1.2,1.4)),
        ('fish_silver',(.235,.04),39,38,(2.4,1.8,2.0)),
        ('fish_blue',(.39,.28),70,40,(3.3,1.2,2.5)),
    ]:
        c=at(*uv,depth)
        for k in range(count):
            place(asset,c+vec((R.gauss(0,spread[0]),R.gauss(0,spread[1]),R.gauss(0,spread[2]))),R.uniform(.35,.65),.1)
    for u,v,depth,scale,yaw in [(.335,.155,36,2.5,-.5),(.46,.225,57,1.8,.3)]:
        target=at(u,v+.012,depth);p=target.copy()
        # Solve only the initial actor translation; local wing motion stays live.
        for _ in range(12):
            residual=vec((p[0]+2*math.sin(.51+p[2])-target[0],p[2]+.45*math.cos(.69+p[0])-target[2]))
            jac=np.array([[1,2*math.cos(.51+p[2])],[-.45*math.sin(.69+p[0]),1]])
            step=np.linalg.solve(jac,residual)
            p[0]-=step[0];p[2]-=step[1]
        place('ray',p,scale,yaw)
    for k in range(65):place('particle',(R.uniform(-15,15),R.uniform(1,22),R.uniform(-55,10)),R.uniform(.5,1.6))
    # Remove only obsolete outputs from the abandoned mesh-baking experiment.
    for stale in list(OUT.glob('ruins_chunk_*')) + [OUT/(n+ext) for n in ('fish_field','fish_blue_field','dust_field') for ext in ('.glb','.model','.go')]:
        if stale.suffix in ('.glb','.model','.go') and stale.exists():stale.unlink()
    (ROOT/'assets/source/landmarks.json').write_text(json.dumps(landmark_records,indent=2)+'\n')
    (ROOT/'main/world.collection').write_text('name: "world"\n'+ '\n'.join(objects)+'\n')
    (ROOT/'main/obstacles.lua').write_text('return '+json.dumps([[float(v) for v in box] for box in obstacles],separators=(',',':')).replace('[','{').replace(']','}')+'\n')
    finish_character()
    finish_ruins()
    STATS['world']={"instances":len(objects),"source_placements":placements,"collision_boxes":len(obstacles),"seed":73}
    (OUT/'manifest.json').write_text(json.dumps(STATS,indent=2)+'\n')
    print(json.dumps(STATS,indent=2))


if __name__=='__main__':main()
