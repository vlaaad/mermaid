"""Bake seamless refractive caustics by splatting a periodic wave's ray field."""
import math
import numpy as np
from PIL import Image, ImageFilter


def surface_normals(size=512):
    """Periodic analytic wave derivatives, prefiltered by the texture mip chain."""
    y,x=np.mgrid[0:size,0:size].astype(np.float32)/size
    dx=np.zeros_like(x);dy=np.zeros_like(y)
    rng=np.random.default_rng(403)
    for _ in range(24):
        kx,ky=rng.integers(-12,13,size=2)
        length=math.hypot(kx,ky)
        if length<2:continue
        slope=np.cos(math.tau*(kx*x+ky*y)+rng.uniform(0,math.tau))*.045/math.sqrt(length/4)
        dx+=slope*kx/length;dy+=slope*ky/length
    # Slopes are stored directly. Runtime finite differences of an 8-bit height
    # texture magnify quantization and expose its texel grid at grazing angles.
    return np.uint8(np.clip(np.stack([dx*.5+.5,dy*.5+.5,np.ones_like(x)],axis=-1),0,1)*255)


def caustics(size=512):
    # Sixteen rays per output texel, filtered offline. No runtime noise loops.
    samples=size*4
    y,x=np.mgrid[0:samples,0:samples].astype(np.float32)/samples
    dx=np.zeros_like(x);dy=np.zeros_like(y)
    for kx,ky,amplitude,phase in [(3,1,.021,.3),(1,4,.018,1.9),(-4,3,.015,3.1),(6,2,.010,2.2),(2,-7,.007,.8),(9,-3,.004,4.2)]:
        wave=np.sin(math.tau*(kx*x+ky*y)+phase)*amplitude
        length=math.hypot(kx,ky)
        dx+=wave*(kx/length);dy+=wave*(ky/length)
    ix=np.floor(((x+dx)%1)*size).astype(np.int32)
    iy=np.floor(((y+dy)%1)*size).astype(np.int32)
    density=np.bincount((iy*size+ix).ravel(),minlength=size*size).reshape(size,size)/16.0
    # Wrap before filtering so the animated projection has no seams.
    padded=np.pad(density,8,mode='wrap')
    image=Image.fromarray(np.uint8(np.clip(padded/6,0,1)*255)).filter(ImageFilter.GaussianBlur(.85))
    density=np.asarray(image,dtype=float)[8:-8,8:-8]*6/255
    return np.clip((density-.72)*.40,0,1)
