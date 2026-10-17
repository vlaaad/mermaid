"""Exercise simultaneous contacts and the actual game input handler in Lua."""
import ctypes,ctypes.util,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class TouchControls(unittest.TestCase):
    def run_lua(self,source):
        path=ctypes.util.find_library('lua5.4') or ctypes.util.find_library('lua5.3')
        if not path:self.skipTest('system Lua library unavailable')
        lib=ctypes.CDLL(path);ptr=ctypes.c_void_p
        lib.luaL_newstate.restype=ptr;lib.luaL_openlibs.argtypes=[ptr]
        lib.luaL_loadstring.argtypes=[ptr,ctypes.c_char_p];lib.luaL_loadstring.restype=ctypes.c_int
        lib.lua_pcallk.argtypes=[ptr,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_longlong,ptr];lib.lua_pcallk.restype=ctypes.c_int
        lib.lua_tolstring.argtypes=[ptr,ctypes.c_int,ptr];lib.lua_tolstring.restype=ctypes.c_char_p;lib.lua_close.argtypes=[ptr]
        state=lib.luaL_newstate();lib.luaL_openlibs(state)
        setup='package.path='+repr(str(ROOT/'?.lua')+';')+'..package.path\nlocal M=require "main.touch_controls"\n'
        try:
            result=lib.luaL_loadstring(state,(setup+source).encode())
            if result==0:result=lib.lua_pcallk(state,0,0,0,0,None)
            self.assertEqual(result,0,(lib.lua_tolstring(state,-1,None) or b'').decode())
        finally:lib.lua_close(state)
    def test_hold_and_swipe_are_independent(self):
        self.run_lua('''
local s=M.new()
local dx,dy=M.apply(s,{{id=1,x=100,y=300},{id=2,x=1000,y=300}},1280,720)
assert(s.forward and dx==0 and dy==0)
dx,dy=M.apply(s,{{id=1,x=110,y=310},{id=2,x=1128,y=372}},1280,720)
assert(s.forward and math.abs(dx-.1)<1e-8 and math.abs(dy-.1)<1e-8)
M.apply(s,{{id=1,x=110,y=310},{id=2,released=true}},1280,720)
assert(s.forward and not s.look_id)
M.apply(s,{},1280,720);assert(not s.forward and not s.look_id)
''')
    def test_role_stays_fixed_and_multiple_left_fingers_release_safely(self):
        self.run_lua('''
local s=M.new()
M.apply(s,{{id=1,x=100,y=100},{id=2,x=200,y=100}},1280,720)
local dx,dy=M.apply(s,{{id=1,x=1100,y=300},{id=2,x=200,y=100}},1280,720)
assert(s.forward and dx==0 and dy==0)
M.apply(s,{{id=1,released=true},{id=2,x=200,y=100}},1280,720);assert(s.forward)
M.reset(s);assert(not s.forward and not next(s.contacts))
''')
    def test_portrait_coordinates_and_secondary_look_finger(self):
        self.run_lua('''
local s=M.new()
M.apply(s,{{id=3,screen_x=300,screen_y=200},{id=4,screen_x=330,screen_y=300}},375,812)
local dx,dy=M.apply(s,{{id=3,released=true},{id=4,screen_x=350,screen_y=400}},375,812)
assert(not s.forward and dx==0 and dy==0 and s.look_id==4)
dx,dy=M.apply(s,{{id=4,screen_x=312.5,screen_y=481.2}},375,812)
assert(math.abs(dx+.1)<1e-8 and math.abs(dy-.1)<1e-8)
''')
    def test_real_handler_ignores_emulated_mouse_and_preserves_keyboard(self):
        self.run_lua('''
for _,name in ipairs({'main.obstacles','main.collision','main.life','main.currents','socket'}) do package.loaded[name]={} end
go={property=function()end};resource={texture=function(p)return p end};hash=function(s)return s end
local captures=0
window={get_size=function()return 1280,720 end,get_mouse_lock=function()return false end,set_mouse_lock=function(v)if v then captures=captures+1 end end}
dofile('''+repr(str(ROOT/'main/main.script'))+''')
local s={ui_contacts={},touch=M.new(),yaw=0,pitch=0,frozen=true,keys={},taps={},mouse_was_locked=false,frames=20,mouse_frame=-1,mouse_ready_frame=0}
on_input(s,'multitouch',{touch={{id=1,x=100,y=300},{id=2,x=1000,y=300}}})
assert(s.touch.forward and not s.frozen and s.yaw==0)
on_input(s,'multitouch',{touch={{id=1,x=100,y=300},{id=2,x=1128,y=372}}})
assert(math.abs(s.yaw+.4096)<1e-8 and math.abs(s.pitch-.216)<1e-8)
on_input(s,'touch',{source='touch',pressed=true,dx=600,dy=100,x=1000,y=300})
assert(captures==0 and not s.steering and math.abs(s.yaw+.4096)<1e-8)
on_input(s,'forward',{source='keyboard',pressed=true})
on_input(s,'multitouch',{touch={}})
assert(s.keys.forward and not s.touch.forward)
s.ui_mouse=true
on_input(s,'forward',{source='keyboard',released=true})
assert(not s.keys.forward and s.ui_mouse)
on_input(s,'touch',{source='mouse',released=true,x=1240,y=690})
assert(not s.ui_mouse)
''')
    def test_invisible_profiler_corner_does_not_interrupt_held_thrust(self):
        self.run_lua('''
local ui=require 'main.game_ui';local contacts={};local s=M.new()
local filtered,events=ui.filter_touches(contacts,{{id=1,x=100,y=300},{id=2,x=1240,y=690}},1280,720)
assert(#filtered==1 and #events==1 and events[1]=='profiler')
M.apply(s,filtered,1280,720);assert(s.forward and not s.look_id)
filtered,events=ui.filter_touches(contacts,{{id=1,x=100,y=300},{id=2,x=1240,y=690}},1280,720)
assert(#events==0)
filtered,events=ui.filter_touches(contacts,{{id=1,x=100,y=300},{id=2,released=true}},1280,720)
M.apply(s,filtered,1280,720);assert(s.forward)
assert(ui.hit(330,770,375,812)=='profiler' and not ui.hit(330,600,375,812))
''')
if __name__=='__main__':unittest.main()
