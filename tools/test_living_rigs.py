"""Check actual skinned geometry, not just animation metadata."""
import math,unittest
from pathlib import Path
import numpy as np
from tools.rig_assets import GLB
ROOT=Path(__file__).resolve().parents[1]

def skinned(g,clip,t):
    d=g.doc;a=next(a for a in d['animations'] if a['name']==clip);nodes=d['nodes'];local={}
    for ch in a['channels']:
        track=a['samplers'][ch['sampler']];times=g.read(track['input'])[:,0];q=g.read(track['output']);i=min(len(times)-2,max(0,np.searchsorted(times,t)-1));f=(t-times[i])/(times[i+1]-times[i]);q=q[i]*(1-f)+q[i+1]*f;q/=np.linalg.norm(q)
        x,y,z,w=q
        r=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
        m=np.eye(4);m[:3,:3]=r;m[:3,3]=nodes[ch['target']['node']].get('translation',[0,0,0]);local[ch['target']['node']]=m
    parents={c:i for i,n in enumerate(nodes) for c in n.get('children',[])};world={}
    def matrix(i):
        if i not in world:world[i]=(matrix(parents[i]) if i in parents else np.eye(4))@local.get(i,np.eye(4))
        return world[i]
    skin=d['skins'][0];inverse=g.read(skin['inverseBindMatrices']).reshape(-1,4,4).transpose(0,2,1)
    palette=np.array([matrix(i)@b for i,b in zip(skin['joints'],inverse)])
    attrs=d['meshes'][0]['primitives'][0]['attributes'];p=g.read(attrs['POSITION']);j=g.read(attrs['JOINTS_0']);w=g.read(attrs['WEIGHTS_0']);p=np.column_stack([p,np.ones(len(p))]);out=np.zeros_like(p)
    for k in range(4):out+=np.einsum('nij,nj->ni',palette[j[:,k]],p)*w[:,k,None]
    return out[:,:3]

class Rigs(unittest.TestCase):
    def test_weight_normalization(self):
        for name in ['mermaid','kelp','ribbon_kelp','fish','fish_blue','fish_orange','fish_silver']:
            g=GLB(ROOT/'assets/generated'/f'{name}.glb');attrs=g.doc['meshes'][0]['primitives'][0]['attributes'];w=g.read(attrs['WEIGHTS_0'])
            self.assertGreaterEqual(float(w.min()),0);self.assertLess(float(abs(w.sum(axis=1)-1).max()),1e-6);self.assertTrue((np.count_nonzero(w,axis=1)<=2).all())
    def test_mermaid_vertical_wave_reaches_fin(self):
        g=GLB(ROOT/'assets/generated/mermaid.glb');a=skinned(g,'swim',.1);b=skinned(g,'swim',1.0)
        attrs=g.doc['meshes'][0]['primitives'][0]['attributes'];alpha=g.read(attrs['COLOR_0'])[:,3];fin=(alpha>.37)&(alpha<.62)
        d=abs(a-b)[fin]
        self.assertGreater(float(np.percentile(np.linalg.norm(d,axis=1),75)),.4)
        self.assertGreater(float(d[:,2].mean()),float(d[:,0].mean())*3)
    def test_hands_and_hair_have_visible_follow_through(self):
        g=GLB(ROOT/'assets/generated/mermaid.glb');attrs=g.doc['meshes'][0]['primitives'][0]['attributes']
        p=g.read(attrs['POSITION']);alpha=g.read(attrs['COLOR_0'])[:,3]
        frames=np.array([skinned(g,'swim',t) for t in np.linspace(0,1.8,13)])
        # Select actual palms/fingers and lock tips by anatomy/material, rather
        # than testing whether animation channels were merely exported.
        for mask in [(p[:,0]<-1.3)&(alpha<.1),
                     (p[:,0]>1.24)&(p[:,1]<.2)&(alpha<.1),
                     (alpha>.62)&(alpha<.87)&(p[:,2]>.85)]:
            self.assertGreater(int(mask.sum()),100)
            travel=np.linalg.norm(np.ptp(frames[:,mask,:],axis=0),axis=1)
            self.assertGreater(float(np.median(travel)),.35)
        # Head/scalp motion alone cannot account for the locks' displacement.
        scalp=(alpha>.62)&(alpha<.87)&(p[:,1]>1.8)
        tips=(alpha>.62)&(alpha<.87)&(p[:,2]>.85)
        relative=frames[:,tips,:].mean(axis=1)-frames[:,scalp,:].mean(axis=1)
        self.assertGreater(float(np.linalg.norm(np.ptp(relative,axis=0))),.30)

    def test_plant_root_fixed_crown_bends(self):
        for name in ['kelp','ribbon_kelp']:
            g=GLB(ROOT/'assets/generated'/f'{name}.glb');a=skinned(g,'bend',0);b=skinned(g,'bend',1)
            p=g.read(g.doc['meshes'][0]['primitives'][0]['attributes']['POSITION']);delta=np.linalg.norm(a-b,axis=1)
            self.assertLess(float(delta[p[:,1]<.025].max()),.004)
            self.assertGreater(float(delta[p[:,1]>p[:,1].max()*.85].mean()),1.0)
if __name__=='__main__':unittest.main()
