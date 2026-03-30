"""
fix_gloves_inner_palm_only.py
==============================
Minimal targeted fix: pushes only the inner (body-facing) palm/finger surfaces
outward in the global -Y direction. The outer/dorsal surface is NOT touched,
so the fingers keep their correct 24mm shape and proportions.

One Gaussian per hand, centred on the inner palm, with a wide sigma that
covers the palm through all fingertips on the inner side only.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python fix_gloves_inner_palm_only.py
"""
import bpy, bmesh, math

BASE   = "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
GLB_IN = f"{BASE}/viewer/public/equipment/shell_gloves.glb"
GLB_OUT = GLB_IN

# Centre on inner palm, wide sigma to reach finger shafts
CENTRES = [
    ( 0.62, -0.050, 1.390),
    (-0.62, -0.050, 1.390),
]
PUSH_PEAK = 0.018   # 18 mm at Gaussian peak
SIGMA     = 0.075   # 7.5 cm — reaches from wrist through finger shafts
CUTOFF    = 3.5     # hard cutoff at 3.5σ ≈ 26 cm

def gauss(px,py,pz,cx,cy,cz,sig):
    d2=(px-cx)**2+(py-cy)**2+(pz-cz)**2
    return math.exp(-d2/(2*sig**2))

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=GLB_IN)
bpy.ops.object.mode_set(mode='OBJECT')

mesh_objs=[o for o in bpy.data.objects if o.type=='MESH' and o.vertex_groups]
armatures=[o for o in bpy.data.objects if o.type=='ARMATURE']

for obj in mesh_objs:
    mesh=obj.data
    bm=bmesh.new(); bm.from_mesh(mesh); bm.verts.ensure_lookup_table()
    cutoff_d=SIGMA*CUTOFF
    moved=0
    for v in bm.verts:
        x,y,z=v.co.x,v.co.y,v.co.z
        if y>=0.0:          # only inner/palm-facing side
            continue
        best=0.0
        for (cx,cy,cz) in CENTRES:
            d=math.sqrt((x-cx)**2+(y-cy)**2+(z-cz)**2)
            if d<cutoff_d:
                best=max(best,gauss(x,y,z,cx,cy,cz,SIGMA))
        if best<0.01: continue
        v.co.y-=PUSH_PEAK*best
        moved+=1
    bm.normal_update(); bm.to_mesh(mesh); bm.free(); mesh.update()
    print(f"[{obj.name}] pushed {moved} inner-palm verts (peak={PUSH_PEAK*1000:.0f}mm, σ={SIGMA*100:.1f}cm)")

bpy.ops.object.select_all(action='DESELECT')
for o in mesh_objs+armatures: o.select_set(True)
if armatures: bpy.context.view_layer.objects.active=armatures[0]

bpy.ops.export_scene.gltf(
    filepath=GLB_OUT, export_format='GLB', use_selection=True,
    export_apply=False, export_yup=True, export_skins=True,
    export_all_influences=True, export_def_bones=True,
    export_animations=False, export_materials='EXPORT',
)
print("Done ✓")
