"""Real glTF skins and sampled joint tracks; no procedural actor vertex warps.

All rigs use at most two joint influences. Rest bone axes share mesh coordinates,
which makes the authored Y-up dolphin stroke easy to inspect in Blender.
"""
import json, math, struct
from pathlib import Path
import numpy as np

class GLB:
    def __init__(self,path):
        self.path=Path(path);data=self.path.read_bytes();n=struct.unpack_from('<I',data,12)[0]
        self.doc=json.loads(data[20:20+n]);self.bin=bytearray(data[28+n:])
    def read(self,index):
        a=self.doc['accessors'][index];v=self.doc['bufferViews'][a['bufferView']]
        width={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
        dtype={5126:'<f4',5123:'<u2',5125:'<u4',5121:'u1'}[a['componentType']]
        result=np.frombuffer(self.bin,dtype=dtype,count=a['count']*width,offset=v.get('byteOffset',0)+a.get('byteOffset',0)).reshape(-1,width).copy()
        if a.get('normalized'):result=result/np.iinfo(result.dtype).max
        return result
    def add(self,values,kind,integer=False):
        a=np.array(values,dtype='<u2' if integer else '<f4');self.bin+=b'\0'*(-len(self.bin)%4)
        views=self.doc['bufferViews'];views.append(dict(buffer=0,byteOffset=len(self.bin),byteLength=a.nbytes));self.bin+=a.tobytes()
        accessor=dict(bufferView=len(views)-1,componentType=5123 if integer else 5126,count=len(a),type=kind)
        if kind=='SCALAR':accessor.update(min=[float(a.min())],max=[float(a.max())])
        self.doc['accessors'].append(accessor);return len(self.doc['accessors'])-1
    def save(self):
        self.bin+=b'\0'*(-len(self.bin)%4);self.doc['buffers'][0]['byteLength']=len(self.bin)
        j=json.dumps(self.doc,separators=(',',':')).encode();j+=b' '*(-len(j)%4)
        payload=struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(self.bin),0x004e4942)+self.bin
        self.path.write_bytes(struct.pack('<III',0x46546c67,2,len(payload)+12)+payload)

def chain_weights(coordinate,knots):
    """Continuous two-bone weights along the anatomical chain."""
    q=np.clip(coordinate,knots[0],knots[-1]);i=np.clip(np.searchsorted(knots,q,side='right')-1,0,len(knots)-2)
    f=np.clip((q-np.array(knots)[i])/(np.array(knots)[i+1]-np.array(knots)[i]),0,1)
    joints=np.zeros((len(q),4),dtype=np.uint16);weights=np.zeros((len(q),4))
    joints[:,0]=i;joints[:,1]=i+1;weights[:,0]=1-f;weights[:,1]=f
    return joints,weights

def rig(path,kind):
    g=GLB(path);d=g.doc
    if d.get('skins'):raise ValueError('Rigging already rigged asset')
    primitive=d['meshes'][0]['primitives'][0];pos=g.read(primitive['attributes']['POSITION']);colors=g.read(primitive['attributes']['COLOR_0'])
    if kind=='mermaid':
        names=['root','tail_upper','tail_middle','tail_lower','peduncle','fin','fin_left','fin_right','hair_root','hair_tip']
        origins=[(0,.14,.065),(.015,-.30,.24),(-.08,-.72,.52),(-.18,-1.03,.79),(-.183,-1.245,1.18),(-.183,-1.40,1.22),(-.60,-1.9,1.4),(.35,-1.9,1.4),(0,1.4,0),(0,.65,.7)]
        parents=[None,0,1,2,3,4,5,5,0,8]
        joints,weights=chain_weights(-pos[:,1],[ -.14,.30,.72,1.03,1.245,1.9])
        # Facial/skin/clothing vertices follow the pelvis; fingers cannot inherit tail weights.
        rigid=(colors[:,3]<.1)|((colors[:,3]>.87))
        joints[rigid]=[0,0,0,0];weights[rigid]=[1,0,0,0]
        fins=(colors[:,3]>.37)&(colors[:,3]<.62)
        f=np.clip((np.abs(pos[:,0]+.183)-.25)/.9,0,.7)
        joints[fins,0]=5;joints[fins,1]=np.where(pos[fins,0]<-.183,6,7)
        weights[fins,0]=1-f[fins];weights[fins,1]=f[fins]
        hair=(colors[:,3]>.62)&(colors[:,3]<.87)
        f=np.clip((1.4-pos[:,1])/.9,0,1)
        joints[hair,0]=8;joints[hair,1]=9;weights[hair,0]=1-f[hair];weights[hair,1]=f[hair]
        clips=['swim','idle'];duration=1.8;frames=49
        def angle(j,t,clip):
            phase=t*math.tau/duration
            amplitude=[.025,.095,.13,.16,.18,.25,.13,.13,.025,.065][j]
            delay=[0,.35,.85,1.35,1.8,2.35,2.85,2.85,.8,1.3][j]
            return amplitude*math.sin(phase-delay)*(1 if clip=='swim' else .18)
        axis=0
    elif kind=='plant':
        height=float(pos[:,1].max());names=['root','stem_1','stem_2','stem_3','crown']
        origins=[(0,height*i/4,0) for i in range(5)];parents=[None,0,1,2,3]
        joints,weights=chain_weights(np.maximum(0,(pos[:,1]-.15)*height/(height-.15)),[p[1] for p in origins]);clips=['bend'];duration=1;frames=3;axis=0
        def angle(j,t,clip):return 0 if j==0 else (t*2-1)*.20
    else:
        names=['body','tail','fluke'];origins=[(0,0,0),(-.22,0,0),(-.38,0,0)];parents=[None,0,1]
        joints,weights=chain_weights(-pos[:,0],[0,.22,.49]);clips=['swim'];duration=.7;frames=25;axis=1
        def angle(j,t,clip):return [0,.16,.30][j]*math.sin(t*math.tau/duration-j*.8)
    node_start=len(d['nodes']);jids=list(range(node_start,node_start+len(names)))
    for j,(name,origin,parent) in enumerate(zip(names,origins,parents)):
        local=np.array(origin)-(np.array(origins[parent]) if parent is not None else 0)
        node=dict(name=name,translation=local.tolist())
        children=[jids[k] for k,p in enumerate(parents) if p==j]
        if children:node['children']=children
        d['nodes'].append(node)
    d['scenes'][0]['nodes'].append(jids[0]);d['nodes'][0]['skin']=0
    inverse=[]
    for origin in origins:
        m=np.eye(4);m[:3,3]=-np.array(origin);inverse.append(m.T.reshape(-1))
    d['skins']=[dict(name=kind+'_skeleton',inverseBindMatrices=g.add(inverse,'MAT4'),joints=jids,skeleton=jids[0])]
    primitive['attributes']['JOINTS_0']=g.add(joints,'VEC4',True);primitive['attributes']['WEIGHTS_0']=g.add(weights,'VEC4')
    d['animations']=[]
    for clip in clips:
        animation=dict(name=clip,samplers=[],channels=[]);times=np.linspace(0,duration,frames);time_accessor=g.add(times,'SCALAR')
        for j in range(len(names)):
            rotations=[]
            for t in times:
                a=angle(j,float(t),clip);q=[0.,0.,0.,math.cos(a/2)];q[axis]=math.sin(a/2);rotations.append(q)
            sampler=len(animation['samplers']);animation['samplers'].append(dict(input=time_accessor,output=g.add(rotations,'VEC4'),interpolation='LINEAR'))
            animation['channels'].append(dict(sampler=sampler,target=dict(node=jids[j],path='rotation')))
        d['animations'].append(animation)
    g.save()
    model=Path(path).with_suffix('.model');text=model.read_text();resource='/assets/generated/'+Path(path).name
    model.write_text(text+f'skeleton: "{resource}"\nanimations: "{resource}"\n'+('create_go_bones: false\n' if kind!='mermaid' else ''))
    return dict(bones=len(names),clips=clips,max_influences=2)

if __name__=='__main__':
    import sys
    rig(sys.argv[1],sys.argv[2])
