"""Copy Harvest Warden hat; fit and rigid-skin to current Male/Female Rework rigs.
Run with Blender --background --python build_witch_hat.py.
"""
import bpy,bmesh,json,math,shutil
from pathlib import Path
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent
SOURCE=PROJECT/'halloween_shrine/HalloweenOfferingShrine.blend'
PARTS=['Ragged witch brim','Bent witch crown','Hat ochre band','Witch hat buckle','Witch hat buckle.001','Witch hat buckle.002','Witch hat buckle.003','Hanging lantern 4','Enclosed lantern ember core.005','Twisted pumpkin stem.005','Twisted suspension cord.004','Lantern loop.004']

def active(o):
 bpy.ops.object.select_all(action='DESELECT');o.hide_set(False);o.select_set(True);bpy.context.view_layer.objects.active=o

def tree(o):
 deps=bpy.context.evaluated_depsgraph_get();e=o.evaluated_get(deps);me=e.to_mesh()
 t=BVHTree.FromPolygons([e.matrix_world@v.co for v in me.vertices],[list(p.vertices) for p in me.polygons]);e.to_mesh_clear();return t

def export(file,objects):
 active(objects[0])
 for o in objects:o.select_set(True)
 bpy.ops.export_scene.gltf(filepath=str(file),export_format='GLB',use_selection=True,export_skins=True,export_animations=False,export_yup=True,export_all_influences=False,export_extras=True)

report={};slots=[]
for sex,sx,sy,brim,cy in [('Male',.235,.28,1.757,.012),('Female',.225,.27,1.742,.022)]:
 bpy.ops.wm.read_factory_settings(use_empty=True)
 bpy.ops.import_scene.gltf(filepath=str(PROJECT/f'viewer/public/models/Base{sex}Rework.glb'))
 body=next(o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('Base'+sex))
 arm=next(m.object for m in body.modifiers if m.type=='ARMATURE')
 for o in list(bpy.data.objects):
  if o.type=='MESH' and o!=body:bpy.data.objects.remove(o,do_unlink=True)
 with bpy.data.libraries.load(str(SOURCE),link=False) as (a,b):
  assert all(n in a.objects for n in PARTS);b.objects=list(PARTS)
 pieces=[]
 for original,o in zip(PARTS,b.objects):
  bpy.context.collection.objects.link(o);o.hide_render=False;o.hide_set(False);o.name=sex+'_'+original
  # The monument crown and band have caps. Remove these to make a true head opening.
  if original in ['Bent witch crown','Hat ochre band']:
   bm=bmesh.new();bm.from_mesh(o.data)
   caps=[f for f in bm.faces if len(f.verts)==12]
   if original=='Bent witch crown':caps=[f for f in caps if f.calc_center_median().z<4.8]
   bmesh.ops.delete(bm,geom=caps,context='FACES');bm.to_mesh(o.data);bm.free()
  # Preserve the copied silhouette and colours. Tailor the opening to head depth.
  W=o.matrix_world.copy()
  for v in o.data.vertices:
   p=W@v.co
   if original=='Twisted suspension cord.004':
    t=max(0,min(1,(p.z-5.30)/.18));p+=Vector((-.055,.01,.02))*t
   v.co=(p.x*sx,(p.y-.05)*sy+cy,(p.z-4.68)*sx+brim)
  o.matrix_world=Matrix.Identity(4)
  o.vertex_groups.clear();vg=o.vertex_groups.new(name='mixamorig:Head');vg.add(list(range(len(o.data.vertices))),1,'REPLACE')
  o.parent=arm;o.matrix_parent_inverse=arm.matrix_world.inverted()
  o.modifiers.new('Rigid head attachment','ARMATURE').object=arm
  o['copied_from']=original;o['attachment']='mixamorig:Head';pieces.append(o)
 # Rebuild the lower crown as a continuous transition from the brim opening.
 # The monument used independent rings with different tilts and radii, leaving
 # a visible slit after its pumpkin head was replaced by the smaller human head.
 brim_obj=pieces[0];crown=pieces[1]
 lower=[brim_obj.data.vertices[i].co.copy() for i in range(40)]
 upper=[crown.data.vertices[i].co.copy() for i in range(12,24)]
 bm=bmesh.new();bm.from_mesh(crown.data);bm.verts.ensure_lookup_table()
 bmesh.ops.delete(bm,geom=[bm.verts[i] for i in range(12)],context='VERTS')
 bm.to_mesh(crown.data);bm.free()
 center=Vector((0,cy,brim))
 def ordered(points):
  return sorted(points,key=lambda p:math.atan2(p.y-center.y,p.x-center.x))
 lower=ordered(lower);upper=ordered(upper);verts=lower+upper
 events=sorted([(math.atan2(p.y-center.y,p.x-center.x),0,i) for i,p in enumerate(lower)]+[(math.atan2(p.y-center.y,p.x-center.x),1,i+40) for i,p in enumerate(upper)])
 last=[39,51];faces=[]
 for angle,ring,index in events:
  faces.append((last[0],index,last[1]))
  last[ring]=index
 me=bpy.data.meshes.new('Continuous crown to brim');me.from_pydata(verts,[],faces);me.update()
 seam=bpy.data.objects.new(sex+'_Crown brim seam',me);bpy.context.collection.objects.link(seam)
 me.materials.append(brim_obj.data.materials[0])
 colors=me.color_attributes.new(name='Color',type='BYTE_COLOR',domain='CORNER')
 for c in colors.data:c.color=(.105,.032,.17,1)
 seam.vertex_groups.new(name='mixamorig:Head').add(list(range(len(verts))),1,'REPLACE')
 seam.parent=arm;seam.matrix_parent_inverse=arm.matrix_world.inverted()
 seam.modifiers.new('Rigid head attachment','ARMATURE').object=arm
 seam['attachment']='mixamorig:Head';pieces.append(seam)
 # Both transition boundaries coincide exactly with their adjacent source rings.
 seam_error=max(max(min((v-p).length for v in verts) for p in ring) for ring in (lower,upper))
 assert seam_error<1e-7
 # Derive the gold band from the actual lower-crown triangles. The original
 # independent tube crossed the repaired crown on the sides and at the back.
 # Clip a continuous strip in the crown's bottom-to-top parameter, then offset
 # it radially. Shared vertices keep every panel joined around the full loop.
 band=pieces[2];band_mat=band.data.materials[0]
 def clip_strip(poly,limit,keep_above):
  result=[]
  for a,b in zip(poly,poly[1:]+poly[:1]):
   ina=a[1]>=limit if keep_above else a[1]<=limit
   inb=b[1]>=limit if keep_above else b[1]<=limit
   if ina:result.append(a)
   if ina!=inb:
    f=(limit-a[1])/(b[1]-a[1]);result.append((a[0].lerp(b[0],f),limit))
  return result
 band_verts=[];band_faces=[];lookup={}
 for face in faces:
  poly=[(verts[i].copy(),0.0 if i<40 else 1.0) for i in face]
  poly=clip_strip(clip_strip(poly,.12,True),.86,False)
  if len(poly)<3:continue
  indices=[]
  for point,t in poly:
   point.x=center.x+(point.x-center.x)*1.035
   point.y=center.y+(point.y-center.y)*1.035
   key=tuple(round(v,7) for v in point)
   if key not in lookup:lookup[key]=len(band_verts);band_verts.append(point)
   indices.append(lookup[key])
  band_faces.append(indices)
 band.data=bpy.data.meshes.new('Crown conforming continuous gold band')
 band.data.from_pydata(band_verts,[],band_faces);band.data.update();band.data.materials.append(band_mat)
 colors=band.data.color_attributes.new(name='Color',type='BYTE_COLOR',domain='CORNER')
 for c in colors.data:c.color=(.50,.24,.065,1)
 band.vertex_groups.clear();band.vertex_groups.new(name='mixamorig:Head').add(list(range(len(band_verts))),1,'REPLACE')
 active(band)
 thickness=band.modifiers.new('Gold band thickness','SOLIDIFY');thickness.thickness=.0008;thickness.offset=-1
 bpy.ops.object.modifier_apply(modifier=thickness.name)
 bpy.context.view_layer.update()
 band_intersections=sum(len(tree(band).overlap(tree(other))) for other in (brim_obj,crown,seam))
 bm=bmesh.new();bm.from_mesh(band.data)
 band_boundary_edges=sum(e.is_boundary for e in bm.edges);bm.free()
 assert band_intersections==0,('gold band clips fabric',band_intersections)
 assert band_boundary_edges==0,('gold band is not closed',band_boundary_edges)
 # Full-detail source stays editable. Pack base textures for a portable fit scene.
 source_collection=bpy.data.collections.new('EDITABLE_HAT_PARTS');bpy.context.scene.collection.children.link(source_collection)
 for o in pieces:
  for c in list(o.users_collection):c.objects.unlink(o)
  source_collection.objects.link(o)
 # Three material batches in a single wearable, all rigidly head weighted.
 copies=[]
 for o in pieces:
  d=o.copy();d.data=o.data.copy();bpy.context.collection.objects.link(d);copies.append(d)
 active(copies[0])
 for o in copies[1:]:o.select_set(True)
 bpy.ops.object.join();hat=bpy.context.object;hat.name=sex+'_HalloweenWitchHat'
 # Remove unused source object metadata on the consolidated wearable.
 for k in list(hat.keys()):del hat[k]
 tri=hat.modifiers.new('Game triangles','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tri.name)
 for a in list(hat.data.uv_layers):hat.data.uv_layers.remove(a)
 bpy.context.view_layer.update()
 intersections=tree(body).overlap(tree(hat))
 vs=[hat.matrix_world@v.co for v in hat.data.vertices]
 bounds=[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]]
 stats={'triangles':len(hat.data.polygons),'vertices':len(vs),'head_bone':'mixamorig:Head','head_weight':1.0,'body_intersecting_triangle_pairs':len(intersections),'bounds_blender_z_up':bounds,'fit_scale_xyz':[sx,sy,sx],'brim_center_z':brim,'source_parts':PARTS,'crown_brim_seam_max_error_m':seam_error,'gold_band_fabric_intersections':band_intersections,'gold_band_boundary_edges':band_boundary_edges}
 
 if intersections:
  dg=bpy.context.evaluated_depsgraph_get();ev=hat.evaluated_get(dg);me=ev.to_mesh()
  print('INTERSECTIONS',[(i,j,list(ev.matrix_world@me.polygons[j].center)) for i,j in intersections],flush=True);ev.to_mesh_clear()
  bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'fit_debug.blend'))
  raise RuntimeError('fit intersections')
 dest=ROOT/sex;dest.mkdir(exist_ok=True)
 export(dest/'WitchHat.glb',[hat,arm])
 public=PROJECT/f'viewer/public/equipment/Rework/HalloweenWitchHat/{sex}';public.mkdir(parents=True,exist_ok=True);shutil.copy2(dest/'WitchHat.glb',public/'WitchHat.glb')
 # Save a fully assembled inspection GLB as well; this is not the wearable export.
 for o in pieces:o.hide_render=True;o.hide_set(True)
 export(dest/'FittedPreview.glb',[hat,arm,body])
 bpy.ops.file.pack_all()
 scene=bpy.context.scene
 scene['fit_notes']='Copied monument witch hat and small hanging pumpkin. Face remains visible; 100% Head weights.'
 # Simple close-up studio showing forehead clearance, not a replaced pumpkin head.
 scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
 scene.render.resolution_x=1200;scene.render.resolution_y=1200;scene.render.resolution_percentage=100
 scene.world=bpy.data.worlds.new('Hat studio');scene.world.color=(.16,.16,.16);scene.view_settings.view_transform='AgX'
 for loc,power,size in [((-2,-3,4),230,3),((2,-1,3),160,2),((0,2,4),260,2)]:
  bpy.ops.object.light_add(type='AREA',location=loc);l=bpy.context.object;l.data.energy=power;l.data.shape='DISK';l.data.size=size;l.rotation_euler=(Vector((0,0,1.7))-l.location).to_track_quat('-Z','Y').to_euler()
 bpy.ops.object.camera_add(location=(.65,-1.7,1.99));cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=.91;scene.camera=cam
 def camera(loc):cam.location=loc;cam.rotation_euler=(Vector((0,0,1.74))-cam.location).to_track_quat('-Z','Y').to_euler()
 camera((.65,-1.7,1.99))
 for screen in bpy.data.screens:
  for area in screen.areas:
   if area.type=='VIEW_3D':
    area.spaces.active.region_3d.view_distance=1.5;area.spaces.active.region_3d.view_location=(0,0,1.73);area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion();area.spaces.active.shading.type='MATERIAL'
 active(hat);bpy.ops.wm.save_as_mainfile(filepath=str(dest/f'{sex}_HalloweenWitchHat.blend'))
 for name,loc in [('front',(0,-1.7,1.85)),('three_quarter',(.8,-1.7,2.05)),('side',(1.7,-.05,1.9)),('top',(0,-.001,3.7)),('above',(.55,-.8,2.8)),('back',(0,1.7,2.05)),('left',(-1.7,0,2.05)),('back_above',(-.65,.9,2.7))]:
  camera(loc);scene.render.filepath=str(dest/(name+'.png'));bpy.ops.render.render(write_still=True)
 # A non-rest head rotation must move every hat vertex with the same rigid transform.
 head=arm.pose.bones['mixamorig:Head'];rest=(arm.matrix_world@head.matrix).copy()
 head.rotation_mode='XYZ';head.rotation_euler=(math.radians(12),math.radians(-18),math.radians(25));bpy.context.view_layer.update()
 delta=(arm.matrix_world@head.matrix)@rest.inverted();dg=bpy.context.evaluated_depsgraph_get();ev=hat.evaluated_get(dg);me=ev.to_mesh()
 error=max(((ev.matrix_world@v.co)-(delta@vs[v.index])).length for v in me.vertices);ev.to_mesh_clear();stats['head_pose_max_error_m']=error;assert error<1e-5,error
 camera((.8,-1.7,2.05));scene.render.filepath=str(dest/'head_turn.png');bpy.ops.render.render(write_still=True)
 report[sex]=stats
 slots.append({'id':f'halloween_witch_rework_{sex.lower()}_helmet','name':f'Halloween Witch Hat ({sex})','collection':'halloween_witch_rework','category':'equipment','gender':sex.lower()+'_rework','wear_slot':'helmet','bilateral':False,'color':'#6e368f','bones':[{'name':'mixamorigHead','weight':1}],'bounds':{'z_min':bounds[0][2],'z_max':bounds[1][2],'radius':max(abs(bounds[0][0]),abs(bounds[1][0]))},'rules':{},'hides_body_regions':[],'mesh_type':'external','mesh_params':{'triangles':stats['triangles'],'revision':3},'url':f'/equipment/Rework/HalloweenWitchHat/{sex}/WitchHat.glb?v=3'})
 (ROOT/'fit_report.json').write_text(json.dumps(report,indent=2))
 print('FIT',sex,json.dumps(stats),flush=True)
spec={'meta':{'version':'1.0','description':'Harvest Warden purple witch hat and small pumpkin charm, individually fitted to Rework bases. Rigid Head skinning; keeps face visible.','rig':'mixamo','coordinate_system':{'up':'+Z','forward':'-Y','right':'+X','scale':'meters'}},'slots':slots}
(ROOT/'equipment_spec_halloween_witch_rework.json').write_text(json.dumps(spec,indent=2))
shutil.copy2(ROOT/'equipment_spec_halloween_witch_rework.json',PROJECT/'viewer/public/equipment/equipment_spec_halloween_witch_rework.json')
