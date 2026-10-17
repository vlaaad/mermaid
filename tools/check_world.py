"""Audit exported collision hulls, plant roots, and individual masonry feet."""
import json
import re
import struct
from pathlib import Path
import numpy as np
from world_geometry import triangles, rotation, Support
from architecture_support import ARCHITECTURE,feet
from bathymetry import mesh_height

ROOT=Path(__file__).resolve().parents[1]

def actors():
    def values(s):return np.array([float(v) for v in re.findall(r'[xyzw]:\s*([-+.\deE]+)',s)])
    pattern=r'instances \{ id: "([^"]+)" prototype: "/assets/generated/([^"/]+).go" position \{([^}]+)\} rotation \{([^}]+)\} scale3 \{([^}]+)\}'
    return [dict(id=i,asset=n,p=values(p),q=values(q),s=values(s)) for i,n,p,q,s in re.findall(pattern,(ROOT/'main/world.collection').read_text())]

def main():
    scene=actors();meshes={};stone=[];rocks=[];owners=[]
    def mesh(name):
        if name not in meshes:meshes[name]=triangles(ROOT/'assets/generated'/f'{name}.glb')
        return meshes[name]
    for a in scene:
        if a['asset'].startswith('rock') or a['asset'] in ('seabed','column','arch','ring','gateway_facade','plinth'):
            world=(mesh(a['asset'])*a['s'])@rotation(a['q']).T+a['p']
            stone.append(world)
            owners.extend([a['id']]*len(world))
            if a['asset'].startswith('rock') or a['asset']=='plinth':rocks.append((a,world.reshape(-1,3)))
    data=(ROOT/'main/obstacles.lua').read_text().removeprefix('return ').replace('{','[').replace('}',']')
    hulls=[b for b in json.loads(data) if len(b)==7]
    hull_centers=np.array([b[:3] for b in hulls]);hull_extents=np.array([b[3:6] for b in hulls])
    errors=[]
    for (a,points),h in zip(rocks,hulls):
        planes=np.array(h[6]);outside=np.max(points@planes[:,:3].T-planes[:,3])
        bound=np.max(abs(points-np.array(h[:3]))-np.array(h[3:6]))
        if outside>.035 or bound>.035:errors.append(dict(id=a['id'],outside=float(outside),bound=float(bound)))
    support=Support(np.concatenate(stone),owners);floating=[];plants=0;worst=0
    for a in scene:
        if a['asset'] not in ('kelp','ribbon_kelp','sponge','coral_pink','coral_blue','coral_gold','amphora'):continue
        plants+=1
        local=mesh(a['asset']).reshape(-1,3)
        roots=np.unique(np.round(local[local[:,1]<.025],3),axis=0)
        # Check every root foot in the shared exported mesh, not just the GO origin.
        roots=(roots*a['s'])@rotation(a['q']).T+a['p']
        gaps=[]
        for p in roots:
            embedded=False
            for index in np.flatnonzero(np.all(abs(p-hull_centers)<=hull_extents+.02,axis=1)):
                planes=np.asarray(hulls[index][6])
                if np.max(planes[:,:3]@p-planes[:,3])<=.025:
                    embedded=True;break
            if embedded:
                gaps.append(0);continue
            h=support.height(p[0],p[2],p[1])
            if h is None:gaps.append(1000)
            else:gaps.append(p[1]-h)
        gap=max(gaps,default=0);worst=max(worst,gap)
        if gap>.15:floating.append(dict(id=a['id'],gap=float(gap)))
    architecture=[];unsupported=[];foundations=[]
    for a in scene:
        is_footing='_footing_' in a['id']
        if a['asset'] not in ARCHITECTURE and not is_footing:continue
        local=mesh(a['asset'])
        groups=feet(a['asset'],local) if not is_footing else [local.reshape(-1,3)[local.reshape(-1,3)[:,1]<local[:,:,1].min()+.001]]
        gaps=[]
        for group in groups:
            world=(group*a['s'])@rotation(a['q']).T+a['p']
            for p in world:
                if p[1]<=mesh_height(p[0],p[2])+.02:gaps.append(0);continue
                embedded=False
                for index in np.flatnonzero(np.all(abs(p-hull_centers)<=hull_extents+.02,axis=1)):
                    # A footing must not validate its own volume.
                    if rocks[index][0]['id']==a['id']:continue
                    planes=np.asarray(hulls[index][6])
                    if np.max(planes[:,:3]@p-planes[:,3])<=.025:embedded=True;break
                if embedded:gaps.append(0);continue
                h=support.height(p[0],p[2],p[1],exclude=a['id'],ceiling=p[1]+1.0)
                gaps.append(float(p[1]-h) if h is not None else 1000)
        entry=dict(id=a['id'],asset=a['asset'],maximum_gap=max(gaps,default=0),feet=len(groups))
        (foundations if is_footing else architecture).append(entry)
        if entry['maximum_gap']>.15:unsupported.append(entry)
    # Include actual bone attachment GOs in the budget, rather than only scenery.
    data=(ROOT/'assets/generated/mermaid.glb').read_bytes();size=struct.unpack_from('<I',data,12)[0]
    bone_count=len(json.loads(data[20:20+size])['skins'][0]['joints'])
    budget=len(scene)+3+3+bone_count
    report=dict(instances=len(scene),total_go_budget=budget,rocks=len(rocks),collision_hulls=len(hulls),uncovered_rocks=errors,plants=plants,floating=floating,maximum_root_gap=float(worst),architecture=architecture,foundations=foundations,unsupported_architecture=unsupported)
    out=ROOT/'artifacts/close-detail/world-audit.json';out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({**{k:v for k,v in report.items() if k not in ('architecture','foundations')},'architecture_count':len(architecture),'foundation_count':len(foundations)},indent=2))
    assert len(rocks)==len(hulls) and not errors, 'Rendered stone is missing collision coverage'
    assert not floating, 'Some plant feet have no nearby supporting surface'
    assert not unsupported, 'Some masonry feet have no supporting surface'
    assert budget<=2048, 'World exceeds the existing instance budget'

if __name__=='__main__':main()
