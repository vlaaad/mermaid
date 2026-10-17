"""Check the complete cruising loops, not only their initial placements."""
import json,math,unittest
from pathlib import Path
from tools.sea_animals import WHALES
from tools.bathymetry import mesh_height
ROOT=Path(__file__).resolve().parents[1]
class Routes(unittest.TestCase):
    def test_whales_clear_stone_floor_and_surface(self):
        obstacles=json.loads((ROOT/'main/obstacles.lua').read_text().removeprefix('return ').replace('{','[').replace('}',']'))
        for r in WHALES:
            for i in range(180):
                a=i*math.tau/180;x,y,z=r['center'];rx,rz=r['radius']
                x+=rx*math.cos(a);z+=rz*math.sin(a);y+=r['height']*math.sin(2*a)
                # Larger than the scaled, swimming geometry, including drift.
                self.assertGreater(y-9-mesh_height(x,z),5)
                self.assertLess(y+8,49)
                for b in obstacles:
                    overlap=abs(x-b[0])<b[3]+24 and abs(z-b[2])<b[5]+24 and y-9<b[1]+b[4] and y+8>b[1]-b[4]
                    self.assertFalse(overlap,(r['id'],i,b[:6]))
    def test_whales_start_in_the_distance(self):
        for r in WHALES:
            x,y,z=r['center'];rx,rz=r['radius'];a=r['phase'];p=[x+rx*math.cos(a),y+r['height']*math.sin(a*2),z+rz*math.sin(a)]
            self.assertGreater(math.dist(p,[-1,4.8,4]),110)
            self.assertGreater(r['scale']*9,30)
if __name__=='__main__':unittest.main()
