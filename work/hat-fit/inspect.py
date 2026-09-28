import bpy,json
from pathlib import Path
root=Path.cwd()
for sex in ['Female','Male']:
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 bpy.ops.import_scene.gltf(filepath=str(root/f'viewer/public/appearance/v6/Models/Base{sex}_Appearance.glb'))
 arm=next(o for o in bpy.data.objects if o.type=='ARMATURE')
 head=next(b for b in arm.data.bones if b.name.replace(':','')=='mixamorigHead')
 print(sex,'HEAD',list(arm.matrix_world@head.head_local),'TAIL',list(arm.matrix_world@head.tail_local))
 for o in bpy.data.objects:
  if o.type!='MESH':continue
  vs=[o.matrix_world@v.co for v in o.data.vertices if v.co.z>0] # head use bone group
  group=o.vertex_groups.get(head.name)
  if group:vs=[o.matrix_world@v.co for v in o.data.vertices if any(g.group==group.index and g.weight>.5 for g in v.groups)]
  if vs:print(o.name,'HEAD BOUNDS',[[round(f(v[i] for v in vs),4) for i in range(3)] for f in [min,max]])
