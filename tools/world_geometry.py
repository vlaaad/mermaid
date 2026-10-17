"""Geometry queries shared by world generation and collision/support audits."""
import json
import struct
import math
import numpy as np


def triangles(path):
    data=path.read_bytes();size=struct.unpack_from('<I',data,12)[0]
    doc=json.loads(data[20:20+size]);binary=data[28+size:]
    def access(index):
        a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']]
        width={'SCALAR':1,'VEC3':3}[a['type']]
        return np.frombuffer(binary,dtype={5126:'<f4',5125:'<u4',5123:'<u2'}[a['componentType']],count=a['count']*width,offset=v.get('byteOffset',0)+a.get('byteOffset',0)).reshape(-1,width)
    result=[]
    for primitive in doc['meshes'][0]['primitives']:
        vertices=access(primitive['attributes']['POSITION'])
        indices=access(primitive['indices']).ravel() if 'indices' in primitive else np.arange(len(vertices))
        result.append(vertices[indices].reshape(-1,3,3))
    return np.concatenate(result)


def rotation(q):
    x,y,z,w=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])


def convex_collider(tri):
    points=tri.reshape(-1,3);lo=points.min(axis=0);hi=points.max(axis=0)
    center=(lo+hi)*.5;extent=(hi-lo)*.5
    planes=[]
    for a,b,c in tri:
        n=np.cross(b-a,c-a);length=np.linalg.norm(n)
        if length<1e-8:continue
        n/=length
        if np.dot(n,a-center)<0:n=-n
        # The small bevel details stay inside this envelope.
        d=np.max(points@n)
        plane=np.round([*n,d],6).tolist()
        if not any(np.dot(n,p[:3])>.9999 for p in planes):planes.append(plane)
    return [*np.round(center,5),*np.round(extent+.015,5),planes]


class Support:
    def __init__(self,tri,owners=None):
        self.owners=np.asarray(owners) if owners is not None else None
        self.a=tri[:,0];self.ab=tri[:,1]-self.a;self.ac=tri[:,2]-self.a
        normal=np.cross(self.ab,self.ac)
        self.det=self.ab[:,0]*self.ac[:,2]-self.ab[:,2]*self.ac[:,0]
        self.valid=(normal[:,1]>np.linalg.norm(normal,axis=1)*.30)&(np.abs(self.det)>1e-9)
        self.safe=np.where(self.valid,self.det,1)
        self.cells={};self.global_triangles=[]
        lo=np.floor(tri[:,:,[0,2]].min(axis=1)/8).astype(int)
        hi=np.floor(tri[:,:,[0,2]].max(axis=1)/8).astype(int)
        for i in np.flatnonzero(self.valid):
            lx,lz=lo[i];hx,hz=hi[i]
            if (hx-lx+1)*(hz-lz+1)>256:self.global_triangles.append(i);continue
            for x in range(lx,hx+1):
                for z in range(lz,hz+1):self.cells.setdefault((x,z),[]).append(i)
        self.cells={key:np.array(value+self.global_triangles,dtype=int) for key,value in self.cells.items()}
    def height(self,x,z,near,exclude=None,ceiling=None):
        ids=self.cells.get((math.floor(x/8),math.floor(z/8)),self.global_triangles)
        if exclude is not None and self.owners is not None:
            ids=np.asarray(ids);ids=ids[self.owners[ids]!=exclude]
        a,ab,ac=self.a[ids],self.ab[ids],self.ac[ids]
        dx=x-a[:,0];dz=z-a[:,2]
        u=(dx*ac[:,2]-dz*ac[:,0])/self.safe[ids]
        v=(ab[:,0]*dz-ab[:,2]*dx)/self.safe[ids]
        hit=(u>=-1e-6)&(v>=-1e-6)&(u+v<=1.000001)
        h=(a[:,1]+u*ab[:,1]+v*ac[:,1])[hit]
        if ceiling is not None:h=h[h<=ceiling]
        return float(h[np.argmin(abs(h-near))]) if len(h) else None
