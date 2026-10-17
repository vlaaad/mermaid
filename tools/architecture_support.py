"""Actual exported load-bearing feet; window walls may rest on another arcade."""
import numpy as np
from bathymetry import mesh_height

ARCHITECTURE=('column','arch','gateway_facade','ring')

def feet(asset,tri):
    points=np.unique(np.round(tri.reshape(-1,3),5),axis=0)
    if asset in ('column','ring'):
        return [points[points[:,1]<points[:,1].min()+.025]]
    # Each pier must have its own support, including the secondary arcade.
    centers=[-2.2,2.2] if asset=='arch' else [-3.14,-2.2,2.2,3.14,4.45,8.05,9.02]
    result=[]
    for x in centers:
        leg=points[(abs(points[:,0]-x)<.60)&(abs(points[:,2])<1.05)&(points[:,1]>-.10)]
        result.append(leg[leg[:,1]<leg[:,1].min()+.10])
    return result

def footing_sites(actor,mesh,support):
    from world_geometry import rotation
    mat=rotation(actor['q']);scale=np.asarray(actor['scale']);p=actor['p']
    sites=[]
    for local in feet(actor['asset'],mesh):
        world=(local*scale)@mat.T+p
        def height(v,ceiling):
            h=support.height(v[0],v[2],v[1],exclude=actor['name'],ceiling=ceiling)
            # A deeply buried foot may be below every upward-facing surface.
            return support.height(v[0],v[2],v[1],exclude=actor['name']) if h is None else h
        heights=[height(v,v[1]+1.0) for v in world]
        if any(h is None for h in heights):raise ValueError('No ground below '+actor['name'])
        if max(v[1]-h for v,h in zip(world,heights))<=.15:continue
        # The shared plinth has worn edges; its flat top must still cover the
        # entire original foot, rather than only the column's center point.
        lo,hi=local.min(axis=0),local.max(axis=0)
        center=(lo+hi)*.5;origin=(center*scale)@mat.T+p
        sx=max(.2,(hi[0]-lo[0])*scale[0]*1.18)
        sz=max(.2,(hi[2]-lo[2])*scale[2]*1.18)
        top=float(world[:,1].max()+.10)
        # Sample the footing's full footprint, not only the narrower pier.
        # A narrow shelf can cover the sample points but leave part of a wider
        # footing over empty water. Carry the pier into the continuous seabed.
        terrain=[]
        for dx in (-1,0,1):
            for dz in (-1,0,1):
                v=origin+mat@np.array([dx*sx*.5,0,dz*sz*.5])
                terrain.append(mesh_height(v[0],v[2]))
        bottom=min(terrain)-.30
        sites.append((origin[0],top,origin[2],sx,(top-bottom)/.8,sz))
    return sites
