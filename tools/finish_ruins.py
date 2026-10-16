"""Blender finishing for actual masonry meshes: erosion, edge bevels, weighted normals.

Invoked by build_assets.py. Editable source: assets/source/ruins.blend.
"""
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import noise

source = Path(sys.argv[sys.argv.index('--')+1])
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
objects = []
shared_material = None
names=sys.argv[sys.argv.index('--')+2:] or ['column', 'arch', 'ring', 'gateway_facade']
for name in names:
    bpy.ops.import_scene.gltf(filepath=str(source/f'{name}-procedural.glb'))
    obj = next(o for o in bpy.context.selected_objects if o.type == 'MESH')
    obj.name = name
    bpy.context.view_layer.objects.active = obj
    bm = bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=.00001)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data);bm.free()
    # Small physical erosion: preserve overall dimensions, passage clearance and seams.
    for vertex in obj.data.vertices:
        p = vertex.co.copy()
        amount = noise.noise(p*3.7, noise_basis='PERLIN_ORIGINAL')*(.012 if name.startswith('rock') else .024)
        vertex.co += vertex.normal*amount
    bevel = obj.modifiers.new('Worn masonry edges', 'BEVEL')
    bevel.width=.035 if name.startswith('rock') else .045;bevel.segments=2;bevel.limit_method='ANGLE';bevel.angle_limit=.65
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    for face in obj.data.polygons:face.use_smooth=True
    weighted = obj.modifiers.new('Broad stone face normals', 'WEIGHTED_NORMAL')
    weighted.keep_sharp=True;weighted.weight=50
    bpy.ops.object.modifier_apply(modifier=weighted.name)
    attribute = obj.data.color_attributes.active_color or obj.data.color_attributes[0]
    for face in obj.data.polygons:
        for loop_index in face.loop_indices:
            index = loop_index if attribute.domain=='CORNER' else obj.data.loops[loop_index].vertex_index
            vertex = obj.data.vertices[obj.data.loops[loop_index].vertex_index]
            color = attribute.data[index].color[:]
            mottling=.96+.06*noise.noise(vertex.co*1.6, noise_basis='PERLIN_ORIGINAL')
            attribute.data[index].color=(*(min(1,max(0,c*mottling)) for c in color[:3]),color[3])
    obj.data.color_attributes.active_color=attribute
    if shared_material is None:
        shared_material=obj.data.materials[0];shared_material.name='reef'
    obj.data.materials.clear();obj.data.materials.append(shared_material)
    for face in obj.data.polygons:face.material_index=0
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
    props=bpy.ops.export_scene.gltf.get_rna_type().properties['export_vertex_color'].enum_items
    bpy.ops.export_scene.gltf(filepath=str(source/f'{name}-finished.glb'),export_format='GLB',use_selection=True,
                             export_animations=False,export_cameras=False,export_lights=False,
                             export_vertex_color='ACTIVE' if 'ACTIVE' in props.keys() else 'MATERIAL',
                             export_normals=True,export_texcoords=True)
    objects.append(obj)
    print('MASONRY_FINISHED',name,'faces',len(obj.data.polygons),'vertices',len(obj.data.vertices))
for i,obj in enumerate(objects):obj.location.x=i*12
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(source/('rocks.blend' if names[0].startswith('rock') else 'ruins.blend')))
