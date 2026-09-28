"""Fit source Alpha Pass hats and rigidly skin them to each character's head.
Run: Blender --background --python scripts/fit_alpha_pass_hats.py
Original unrigged GLBs remain in AlphaPass/; fitted exports go in sex folders.
"""
from pathlib import Path
import bpy
import json
import base64
import struct
import math
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'viewer/public'
# Uniform scale and brim height relative to the female appearance skull crown.
# Fit the wearable portion, not the full decorative bounding box (plumes/crystals).
FITS = {
    'Inventioners': (0.29, -0.1167, 0.015),
    'Boghop': (0.46, -0.0767, 0.015),
    'Shardspire': (0.30, -0.0967, 0.015),
    'Wayfinder': (0.48, -0.1067, 0.010),
    'Wildplume': (0.33, -0.0967, 0.010),
}

HAIR_ROOM = 1.12  # More room around the hairstyle without lifting the brim.
profiles = {}

def coverage(meshes, size=64):
    """Rasterize the hat's lowest surface in each vertical column, in glTF axes.
    Generated from geometry alone; every hairstyle uses the same coverage map.
    """
    points = [(v.co.x, -v.co.y, v.co.z) for o in meshes for v in o.data.vertices]
    x0, z0 = min(p[0] for p in points), min(p[1] for p in points)
    x1, z1 = max(p[0] for p in points), max(p[1] for p in points)
    heights = [65535] * (size * size)
    for obj in meshes:
        obj.data.calc_loop_triangles()
        for tri in obj.data.loop_triangles:
            pts = [obj.data.vertices[i].co for i in tri.vertices]
            a, b, c = [((p.x-x0)/(x1-x0)*size, (-p.y-z0)/(z1-z0)*size, p.z) for p in pts]
            denom = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(denom) < 1e-10:
                continue
            for z in range(max(0, math.floor(min(p[1] for p in (a,b,c)))), min(size, math.ceil(max(p[1] for p in (a,b,c))))):
                for x in range(max(0, math.floor(min(p[0] for p in (a,b,c)))), min(size, math.ceil(max(p[0] for p in (a,b,c))))):
                    u = ((b[1]-c[1])*(x+.5-c[0])+(c[0]-b[0])*(z+.5-c[1]))/denom
                    v = ((c[1]-a[1])*(x+.5-c[0])+(a[0]-c[0])*(z+.5-c[1]))/denom
                    w = 1-u-v
                    if min(u,v,w) >= -1e-7:
                        h = round((u*a[2]+v*b[2]+w*c[2])*1000)
                        heights[z*size+x] = min(heights[z*size+x], h)
    packed = struct.pack('<'+'H'*len(heights), *[0 if h==65535 else h for h in heights])
    return {'size':size, 'bounds':[x0,z0,x1-x0,z1-z0], 'heights':base64.b64encode(packed).decode()}

def clear():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

for sex, source in [
    ('Female', 'appearance/v6/Models/BaseFemale_Appearance.glb'),
    ('Male', 'appearance/v6/Models/BaseMale_Appearance.glb'),
    ('Legacy', 'models/BaseFemaleV3.glb'),
]:
    clear()
    bpy.ops.import_scene.gltf(filepath=str(PUBLIC / source))
    rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    head = next(b for b in rig.data.bones if b.name.replace(':', '') == 'mixamorigHead')
    head_points = []
    for obj in list(bpy.context.scene.objects):
        if obj.type != 'MESH':
            continue
        group = obj.vertex_groups.get(head.name)
        if group:
            head_points.extend(obj.matrix_world @ v.co for v in obj.data.vertices
                               if any(g.group == group.index and g.weight > .5 for g in v.groups))
    crown = max(p.z for p in head_points)
    width = max(p.x for p in head_points) - min(p.x for p in head_points)
    size_ratio = width / .194
    profiles[sex] = {}
    # Export only the rig and hat. Body/custom bone display meshes are not equipment.
    for obj in list(bpy.context.scene.objects):
        if obj != rig:
            bpy.data.objects.remove(obj, do_unlink=True)
    for name, (scale, brim_offset, center_y) in FITS.items():
        before = set(bpy.context.scene.objects)
        bpy.ops.import_scene.gltf(filepath=str(PUBLIC / 'equipment/AlphaPass' / (name + '.glb')))
        imported = set(bpy.context.scene.objects) - before
        meshes = [o for o in imported if o.type == 'MESH']
        bottom = min((o.matrix_world @ v.co).z for o in meshes for v in o.data.vertices)
        for obj in meshes:
            world = obj.matrix_world.copy()
            for v in obj.data.vertices:
                p = world @ v.co
                v.co = Vector((p.x * scale * size_ratio * HAIR_ROOM,
                               p.y * scale * size_ratio * HAIR_ROOM + center_y,
                               (p.z - bottom) * scale * size_ratio * 1.05 + crown + brim_offset * size_ratio))
            obj.parent = rig
            obj.matrix_parent_inverse = Matrix.Identity(4)
            obj.matrix_world = Matrix.Identity(4)
            obj.vertex_groups.clear()
            obj.vertex_groups.new(name=head.name).add(list(range(len(obj.data.vertices))), 1.0, 'REPLACE')
            obj.modifiers.new('Rigid head attachment', 'ARMATURE').object = rig
            obj.name = f'{name}_{sex}'
        profiles[sex][name.lower()] = coverage(meshes)
        bpy.ops.object.select_all(action='DESELECT')
        rig.select_set(True)
        for obj in meshes:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = rig
        output = PUBLIC / 'equipment/AlphaPass' / sex / (name + '.glb')
        output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.gltf(filepath=str(output), use_selection=True, export_format='GLB',
                                 export_animations=False, export_extras=False, export_cameras=False,
                                 export_lights=False, export_yup=True)
        print(f'FITTED {sex} {name}: crown={crown:.4f}, width={width:.4f}, scale={scale*size_ratio:.4f}')
        for obj in imported:
            bpy.data.objects.remove(obj, do_unlink=True)

# Keep viewer metadata reproducible and give each design its own collection so
# selecting one hat does not enable the other four as cross-sex counterparts.
legacy_spec = PUBLIC / 'equipment/equipment_spec_female_v2.json'
data = json.loads(legacy_spec.read_text())
slots = []
names = {name.lower(): name for name in FITS}
for slot in data['slots']:
    if slot['id'] not in names:
        continue
    name = names[slot['id']]
    slot.update(url=f'/equipment/AlphaPass/Legacy/{name}.glb?v=hair-fit-3',
                wear_slot='helmet', hides_hair=False, hair_fit=slot['id'], collection='alpha_' + slot['id'])
    for sex in ['Male', 'Female']:
        fitted = dict(slot)
        fitted.update(id=f"alpha_{slot['id']}_{sex.lower()}_helmet",
                      gender=sex.lower() + '_rework',
                      url=f'/equipment/AlphaPass/{sex}/{name}.glb?v=hair-fit-3')
        slots.append(fitted)
legacy_spec.write_text(json.dumps(data, indent=2) + '\n')
(PUBLIC / 'equipment/equipment_spec_alpha_pass.json').write_text(
    json.dumps({'meta': data['meta'], 'slots': slots}, indent=2) + '\n')

(PUBLIC.parent / 'src/data/alphaHatHair.json').write_text(json.dumps(profiles, indent=2) + '\n')
