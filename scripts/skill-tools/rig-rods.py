"""Fit grip anchors and guide string to the shaft, excluding reel decorations."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector
P=Path(__file__).resolve().parents[2]/'viewer/public/tools/fishing_rods'
old=json.loads(Path(__file__).with_name('rod-rig.json').read_text());report={}
# Shaft heights in Blender Z-up space, measured independently of the reels.
profiles={
 'enchanted_fishing_rod':[(.22,.12),(.4,.115),(.6,.092),(.8,.047),(.94,.016)],
 'tidecaster':[(.22,.12),(.4,.10),(.6,.077),(.8,-.016),(.94,-.17)],
 'fishing_rod':[(.22,.12),(.4,.105),(.6,.068),(.7,.024)],
 'verdant_fishing_rod':[(.22,.115),(.4,.098),(.6,.033),(.7,-.014)],
 'ethereal_fishing_rod':[(.22,.112),(.4,.092),(.6,.044),(.7,-.017)],
 'crystal_fishing_rod':[(.22,.11),(.4,.079),(.6,.032),(.7,-.005)],
 'skull_fishing_rod':[(.22,.12),(.4,.104),(.6,.032),(.7,-.016)],
 'fungul_fishing_rod':[(.22,.12),(.4,.104),(.6,.032),(.7,-.016)],
}
for path in sorted(P.glob('*.glb')):
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(path))
 for ob in list(bpy.data.objects):
  if ob.name in ['FishingLineGuides','FishingTip','FishingGrip']:bpy.data.objects.remove(ob,do_unlink=True)
 meshes=[o for o in bpy.data.objects if o.type=='MESH']
 edges=[]
 for ob in meshes:
  vs=[ob.matrix_world@v.co for v in ob.data.vertices]
  edges.extend((vs[e.vertices[0]],vs[e.vertices[1]])for e in ob.data.edges)
 def section(x):
  return [a.lerp(b,(x-a.x)/(b.x-a.x))for a,b in edges if abs(b.x-a.x)>1e-8 and min(a.x,b.x)<=x<=max(a.x,b.x)]
 cross=section(-.03)
 grip=Vector((-.03,(min(v.y for v in cross)+max(v.y for v in cross))/2,(min(v.z for v in cross)+max(v.z for v in cross))/2))
 pts=[]
 for x,z in profiles[path.stem]:
  cross=[v for v in section(x) if abs(v.z-z)<.019]
  if not cross:raise ValueError((path.stem,x))
  pts.append(Vector((x,(min(v.y for v in cross)+max(v.y for v in cross))/2,min(v.z for v in cross)-.002)))
 tip=old[path.stem]['tip'];pts.append(Vector((tip[0],-tip[2],tip[1])))
 vertices=[];faces=[]
 for i,pnt in enumerate(pts):
  tangent=(pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)]).normalized();a=tangent.cross(Vector((0,0,1))).normalized();b=tangent.cross(a)
  for j in range(6):vertices.append(pnt+.0011*(a*math.cos(j*math.tau/6)+b*math.sin(j*math.tau/6)))
 for i in range(len(pts)-1):
  for j in range(6):a=i*6+j;b=i*6+(j+1)%6;faces.append((a,b,b+6,a+6))
 mesh=bpy.data.meshes.new('Attached fishing string');mesh.from_pydata(vertices,[],faces);mesh.update();ob=bpy.data.objects.new('FishingLineGuides',mesh);bpy.context.collection.objects.link(ob)
 mat=bpy.data.materials.new('Pale braided fishing line');mat.diffuse_color=(.60,.68,.70,1);mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=mat.diffuse_color;bs.inputs['Roughness'].default_value=.8;mesh.materials.append(mat)
 for name,point in [('FishingTip',pts[-1]),('FishingGrip',grip)]:
  ob=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(ob);ob.location=point
 bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',export_yup=True,export_extras=True)
 report[path.stem]=dict(grip=[grip.x,grip.z,-grip.y],tip=tip,guide_points=[[v.x,v.z,-v.y]for v in pts],string_triangles=len(faces)*2)
Path(__file__).with_name('rod-rig.json').write_text(json.dumps(report,indent=2))
