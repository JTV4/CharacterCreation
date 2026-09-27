import bpy,bmesh,math,json,sys,os
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform,convex_hull_2d
sys.path.insert(0,str(Path(__file__).resolve().parent))

OUT=Path(__file__).resolve().parent.parent
P=Path(os.environ.get('CHARACTER_CREATION_PUBLIC','/Users/stephenvillavaso/Documents/GitHub/CharacterCreation/viewer/public'))
def active(o):
 bpy.ops.object.select_all(action='DESELECT');o.hide_set(False);o.select_set(True);bpy.context.view_layer.objects.active=o

def material(name,color,rough=.65,metal=0,emission=0):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=rough;bs.inputs['Metallic'].default_value=metal
 if emission:bs.inputs['Emission Color'].default_value=(*color,1);bs.inputs['Emission Strength'].default_value=emission
 return m

def mesh(name,vs,fs,mat,bone=None,smooth=False):
 d=bpy.data.meshes.new(name);d.from_pydata(vs,[],fs);d.update();o=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(o);d.materials.append(M[mat] if isinstance(mat,str) else mat)
 for p in d.polygons:p.use_smooth=smooth
 if bone:bind(o,bone)
 return o

def bind(o,bone=None):
 if bone:
  g=o.vertex_groups.get('mixamorig:'+bone) or o.vertex_groups.new(name='mixamorig:'+bone);g.add(list(range(len(o.data.vertices))),1,'REPLACE')
 else:
  groups={g.index:o.vertex_groups.get(g.name) or o.vertex_groups.new(name=g.name) for g in BODY.vertex_groups}
  for v in o.data.vertices:
   q=o.matrix_world@v.co;hit,normal,idx,dist=TREE.find_nearest(q);face=BODY.data.polygons[idx];corners=list(face.vertices)[:3]
   bary=barycentric_transform(hit,*[BODY.data.vertices[k].co for k in corners],Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)))
   weights={}
   for vi,fac in zip(corners,bary):
    for w in BODY.data.vertices[vi].groups:weights[w.group]=weights.get(w.group,0)+w.weight*max(0,fac)
   best=sorted(weights.items(),key=lambda w:-w[1])[:4];total=sum(w for _,w in best)
   for idx,w in best:
    if w>0:groups[idx].add([v.index],w/total,'REPLACE')
 if not any(m.type=='ARMATURE' for m in o.modifiers):o.modifiers.new('Rework skeleton','ARMATURE').object=ARM
 o.parent=ARM;o.matrix_parent_inverse=ARM.matrix_world.inverted()
 return o

def follow_surface(target,source):
 # Decorations use the garment's interpolated weights to remain attached in motion.
 target.vertex_groups.clear()
 for g in source.vertex_groups:target.vertex_groups.new(name=g.name)
 active(target);md=target.modifiers.new('Garment skin weights','DATA_TRANSFER');md.object=source;md.use_vert_data=True;md.data_types_verts={'VGROUP_WEIGHTS'};md.vert_mapping='POLYINTERP_NEAREST'
 bpy.ops.object.datalayout_transfer(modifier=md.name);bpy.ops.object.modifier_apply(modifier=md.name)
 return target

def normals(o):
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(o.data);bm.free()

def thick(o,t=.004):
 active(o);s=o.modifiers.new('Finished edge','SOLIDIFY');s.thickness=t;s.offset=-1;s.use_rim_only=o.name in ['Santa coat','Cotton trousers'];bpy.ops.object.modifier_apply(modifier=s.name)

def join(obs,name):
 active(obs[0])
 for o in obs[1:]:o.select_set(True)
 bpy.ops.object.join();o=bpy.context.object;o.name=name
 active(o);bpy.ops.object.vertex_group_limit_total(limit=4);bpy.ops.object.vertex_group_normalize_all(lock_active=False)
 return o

def h(b):return ARM.matrix_world@ARM.data.bones['mixamorig:'+b].head_local

def tube(name,points,radius,mat,bone=None,sides=8):
 vs=[];fs=[]
 for i,p in enumerate(points):
  p=Vector(p);d=Vector(points[min(i+1,len(points)-1)])-Vector(points[max(0,i-1)])
  d.normalize();u=d.cross(Vector((0,1,0)))
  if u.length<.01:u=d.cross(Vector((1,0,0)))
  u.normalize();v=d.cross(u);r=radius[i] if isinstance(radius,list) else radius
  for j in range(sides):vs.append(p+r*(u*math.cos(j*2*math.pi/sides)+v*math.sin(j*2*math.pi/sides)))
 for i in range(len(points)-1):
  for j in range(sides):a=i*sides+j;b=i*sides+(j+1)%sides;fs.append((a,b,b+sides,a+sides))
 fs.extend([tuple(reversed(range(sides))),tuple((len(points)-1)*sides+j for j in range(sides))])
 o=mesh(name,vs,fs,mat,bone);normals(o)
 if not bone:bind(o)
 return o

def cube(name,c,scale,mat,bone,bevel=.005):
 bpy.ops.mesh.primitive_cube_add(size=1,location=c);o=bpy.context.object;o.name=name;o.scale=scale;active(o);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 o.data.materials.append(M[mat]);b=o.modifiers.new('Soft leather edges','BEVEL');b.width=bevel;b.segments=1;bpy.ops.object.modifier_apply(modifier=b.name)
 # Bake object positions to keep all export mesh transforms consistent.
 W=o.matrix_world.copy();o.data.transform(W);o.matrix_world=Matrix.Identity(4);bind(o,bone);return o

def ray(z,a,extra=.012):
 c=Vector((0,.02,z));d=Vector((math.sin(a),-math.cos(a),0));hit,_,_,_=TREE.ray_cast(c,d,.32)
 if hit is None:hit=c+d*(.14 if abs(math.sin(a))>.6 else .10)
 return hit+d*extra

def ringmesh(name,rings,mat,bone=None):
 n=len(rings[0]);vs=[p for row in rings for p in row];fs=[]
 for r in range(len(rings)-1):
  for j in range(n):fs.append((r*n+j,r*n+(j+1)%n,(r+1)*n+(j+1)%n,(r+1)*n+j))
 o=mesh(name,vs,fs,mat,bone,True);normals(o)
 if not bone:bind(o)
 return o

def slice_shell(name,lo,hi,xmax,offset,mat,ratio=.6,finish=True):
 foundation=CLEAN
 o=foundation.copy();o.data=foundation.data.copy();bpy.context.collection.objects.link(o);o.name=name;o.hide_render=False;o.hide_set(False)
 bm=bmesh.new();bm.from_mesh(o.data)
 if name=='Cotton trousers':
  bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0001);bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
 for co,no,inner in [((0,0,lo),(0,0,1),True),((0,0,hi),(0,0,1),False),((xmax,0,0),(1,0,0),False),((-xmax,0,0),(1,0,0),True)]:
  bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=.000001,plane_co=co,plane_no=no,clear_inner=inner,clear_outer=not inner)
 bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS');bm.normal_update();bm.to_mesh(o.data);bm.free();o.data.update()
 active(o)
 if o.data.has_custom_normals:bpy.ops.mesh.customdata_custom_splitnormals_clear()
 for f in o.data.polygons:f.use_smooth=True
 md=o.modifiers.new('Cloth ease','DISPLACE');md.direction='NORMAL';md.mid_level=0;md.strength=offset;bpy.ops.object.modifier_apply(modifier=md.name)
 if name=='Soft leather shoes':
  for v in o.data.vertices:
   if v.co.z<.15:
    v.co-=v.normal*max(0,offset-.014)
 if name=='Cotton trousers':
  for v in o.data.vertices:
   if v.co.z<.22:
    v.co-=v.normal*max(0,offset-.006)
 normals(o)
 o.data.materials.clear();o.data.materials.append(M[mat])
 for f in o.data.polygons:f.material_index=0;f.use_smooth=True
 for a in list(o.data.color_attributes):o.data.color_attributes.remove(a)
 active(o)
 if ratio<1:
  md=o.modifiers.new('Garment simplification','DECIMATE');md.ratio=ratio;bpy.ops.object.modifier_apply(modifier=md.name)
 if finish:thick(o,.003)
 return o

def boundary_trim(ob,axis,value,mat,r=.004):
 # Trace the clipped edge on the outside shell as a continuous stitched hem.
 coords=[v.co for v in ob.data.vertices if abs(v.co[axis]-value)<.023]
 if not coords:return []
 # A fitted angular ring gives a tidy hem even where voxel topology is irregular.
 if axis==2:
  n=40;ring=[]
  if value<.6:
   return []
  for j in range(n):ring.append(ray(value,j*math.tau/n,.022))
  return [tube('Bound linen hem',ring+[ring[0]],r,mat)]
 return []

def front(x,z,lift=.030):
 hit,_,_,_=TREE.ray_cast(Vector((x,-.45,z)),Vector((0,1,0)),.9)
 return Vector((x,(hit.y if hit else -.12)-lift,z))

def belt(z,mat='leather',width=.036):
 rows=[]
 tree=BVHTree.FromPolygons([v.co for v in SHIRT_REF.data.vertices],[list(f.vertices) for f in SHIRT_REF.data.polygons])
 for dz in [-width/2+width*i/4 for i in range(5)]:
  row=[]
  for j in range(96):
   a=j*math.tau/96;d=Vector((math.sin(a),-math.cos(a),0));c=Vector((0,.02,z+dz));hit,_,_,_=tree.ray_cast(c+d*.4,-d,.6)
   row.append(hit+d*.026 if hit is not None else ray(z+dz,a,.058))
  rows.append(row)
 ob=ringmesh('Soft waist belt',rows,mat,'Hips');thick(ob,.004)
 y=rows[0][0].y-.01;obs=[ob]
 for x,zz,w,hh in [(0,z+.017,.048,.006),(0,z-.017,.048,.006),(-.024,z,.006,.036),(.024,z,.006,.036)]:obs.append(cube('Simple buckle',(x,y,zz),(w,.010,hh),'brass','Hips',.001))
 return obs

def neckline_height(a,neck):
 return neck-(.100 if FEMALE else .040)*max(0,math.cos(a))**3

def clip_surface(shirt,value):
 src=shirt.data;groupnames=[g.name for g in shirt.vertex_groups];src.calc_loop_triangles();vs=[];fs=[];weights=[]
 for tri in src.loop_triangles:
  poly=[(src.vertices[i].co.copy(),{g.group:g.weight for g in src.vertices[i].groups}) for i in tri.vertices];clipped=[]
  for k,(p,w) in enumerate(poly):
   q,u=poly[(k+1)%len(poly)];a=value(p);b=value(q)
   if a>=0:clipped.append((p,w))
   if (a>=0)!=(b>=0):
    t=a/(a-b);clipped.append((p.lerp(q,t),{g:w.get(g,0)*(1-t)+u.get(g,0)*t for g in set(w)|set(u)}))
  if len(clipped)>=3:
   idx=len(vs);vs.extend(p for p,w in clipped);weights.extend(w for p,w in clipped);fs.append(tuple(range(idx,idx+len(clipped))))
 data=bpy.data.meshes.new('Fitted open neckline');data.from_pydata(vs,[],fs);data.update()
 for m in src.materials:data.materials.append(m)
 shirt.data=data
 shirt.vertex_groups.clear()
 for name in groupnames:shirt.vertex_groups.new(name=name)
 for i,w in enumerate(weights):
  for g,v in w.items():
   if v>0:shirt.vertex_groups[g].add([i],v,'REPLACE')
 bm=bmesh.new();bm.from_mesh(data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(data);bm.free()
 for f in data.polygons:f.use_smooth=True

def open_neckline(shirt,waist,neck):
 # Clip the fitted surface itself, preserving chest contours and skin weights.
 # Interpolate edge crossings so the open neckline has a continuous clean border.
 clip_surface(shirt,lambda p:neckline_height(math.atan2(p.x,.02-p.y),neck)+max(0,abs(p.x)-.09)*.8-p.z)
 data=shirt.data
 # Bind the seam to the actual cut boundary instead of a separate radial outline.
 bm=bmesh.new();bm.from_mesh(data);bm.verts.ensure_lookup_table()
 edges=[e for e in bm.edges if e.is_boundary and all(v.co.z>waist+.12 and abs(v.co.x)<.24 for v in e.verts)]
 adjacency={}
 for e in edges:
  a,b=e.verts;adjacency.setdefault(a.index,[]).append(b.index);adjacency.setdefault(b.index,[]).append(a.index)
 assert adjacency and all(len(neighbors)==2 for neighbors in adjacency.values()), 'Neckline must be a closed boundary'
 start=next(iter(adjacency));ids=[start];previous=None;current=start
 while True:
  choices=[i for i in adjacency[current] if i!=previous]
  if not choices:break
  nxt=choices[0]
  if nxt==start:break
  ids.append(nxt);previous,current=current,nxt
  if len(ids)>len(adjacency):raise RuntimeError('Neckline boundary is not a loop')
 assert len(ids)==len(adjacency), 'Unexpected extra neck openings'
 pts=[bm.verts[i].co.copy() for i in ids];bm.free()
 # Solidify after cutting closes both the inner face and the entire neckline rim.
 shirt['outer_vertex_count']=len(shirt.data.vertices)
 thick(shirt,.004)
 binding=follow_surface(tube('Open neckline binding',pts+[pts[0]],.003,'accent'),shirt)
 # A facing reaches the skin below the bound edge. This closes the air gap
 # even when the viewer removes the body's built-in undergarment faces.
 inner=[]
 for p in pts:
  hit,normal,_,_=TREE.find_nearest(p);inner.append(hit-normal*.003)
 facing=ringmesh('Neckline inner facing',[pts,inner],'cloth');follow_surface(facing,shirt);thick(facing,.002)
 return [binding,facing]

def fit_surface(shirt,clearance_base=.012):
 # Reproject the simplified cloth onto the original faceted skin, especially
 # over shoulder peaks that smoothing the foundation would otherwise erase.
 for v in shirt.data.vertices:
  hit,normal,_,distance=TREE.find_nearest(v.co)
  clearance=max(clearance_base,.014 if abs(v.co.x)>.12 and v.co.z>h('LeftArm').z-.065 else clearance_base)
  if shirt.name=='Linen shirt' and v.co.z<h('Hips').z+.13:clearance=.024
  signed=(v.co-hit).dot(normal)
  if signed<clearance:v.co+=normal*(clearance-signed)
 normals(shirt)
 if shirt.name!='Cotton trousers':shirt.vertex_groups.clear();bind(shirt)


OUTLINES={}
def cloth_outline(z,a,ease):
 # The convex horizontal body section bridges the gap between the thighs
 # without growing the skirt into a cone or indenting it between the legs.
 points=[]
 key=(SEX,round(z,6))
 for edge in ([] if key in OUTLINES else BODY.data.edges):
  p,q=(BODY.data.vertices[i].co for i in edge.vertices)
  if (p.z<=z<q.z) or (q.z<=z<p.z):
   v=p.lerp(q,(z-p.z)/(q.z-p.z));points.append(Vector((v.x,v.y)))
 if key not in OUTLINES:
  if len(points)<3:return ray(z,a,ease)
  OUTLINES[key]=[points[i] for i in convex_hull_2d(points)]
 hull=OUTLINES[key];c=Vector((0,.02));d=Vector((math.sin(a),-math.cos(a)))
 def cross(p,q):return p.x*q.y-p.y*q.x
 radii=[]
 for p,q in zip(hull,hull[1:]+hull[:1]):
  e=q-p;den=cross(d,e)
  if abs(den)<1e-9:continue
  r=cross(p-c,e)/den;t=cross(p-c,d)/den
  if r>=0 and 0<=t<=1:radii.append(r)
 radius=max(radii) if radii else .15
 return Vector((c.x+d.x*(radius+ease),c.y+d.y*(radius+ease),z))


def neckline_height(a,neck):
 return neck-(.135 if FEMALE else .045)*max(0,math.cos(a))**3

def edge_loops(ob,predicate):
 bm=bmesh.new();bm.from_mesh(ob.data);bm.verts.ensure_lookup_table();adj={}
 for e in bm.edges:
  if e.is_boundary and predicate(e):
   a,b=[v.index for v in e.verts];adj.setdefault(a,[]).append(b);adj.setdefault(b,[]).append(a)
 loops=[];seen=set()
 for start in adj:
  if start in seen:continue
  row=[];cur=start;prev=None
  for _ in range(len(adj)+1):
   if cur in seen:break
   seen.add(cur);row.append(bm.verts[cur].co.copy());options=[i for i in adj[cur] if i!=prev]
   if not options:break
   prev,cur=cur,options[0]
  if len(row)>4:loops.append(row)
 bm.free();return loops

def fur_loop(name,pts,radius,source=None):
 # Six-sided sculpted roll, no fur cards, alpha or texture cost.
 # Resample the boundary to avoid tiny bevel segments on triangulated surfaces.
 if (pts[-1]-pts[0]).length>.0001:pts=pts+[pts[0]]
 total=sum((b-a).length for a,b in zip(pts,pts[1:]));count=max(16,int(total/.016));out=[]
 lengths=[0]
 for a,b in zip(pts,pts[1:]):lengths.append(lengths[-1]+(b-a).length)
 k=0
 for i in range(count):
  d=total*i/count
  while k<len(pts)-2 and lengths[k+1]<d:k+=1
  t=(d-lengths[k])/max(1e-9,lengths[k+1]-lengths[k]);out.append(pts[k].lerp(pts[k+1],t))
 out.append(out[0]);o=tube(name,out,[radius*(1+.07*math.cos(i*2.4)) for i in range(len(out))],'fur',sides=6)
 if source:follow_surface(o,source)
 return o

def upper_santa():
 global SHIRT_REF
 waist=h('Hips').z+.022;neck=h('Neck').z+.017;end=abs(h('LeftHand').x)-.022
 shirt=slice_shell('Santa coat',waist-.015,neck+.14,end,.017,'red',.24,False);fit_surface(shirt,.016)
 clip_surface(shirt,lambda p:neckline_height(math.atan2(p.x,.02-p.y),neck)+max(0,abs(p.x)-.09)*.8-p.z)
 necks=edge_loops(shirt,lambda e:all(v.co.z>waist+.12 and abs(v.co.x)<.24 for v in e.verts))
 cuffs=edge_loops(shirt,lambda e:all(abs(v.co.x)>end-.026 for v in e.verts))
 hems=edge_loops(shirt,lambda e:all(v.co.z<waist+.04 for v in e.verts))
 obs=[shirt];thick(shirt,.003)
 for pts in necks:
  obs.append(fur_loop('Ivory neckline roll',pts,.016,shirt))
  inner=[]
  for p in pts:
   hit,normal,_,_=TREE.find_nearest(p);inner.append(hit-normal*.003)
  facing=ringmesh('Neckline inner facing',[pts,inner],'red');follow_surface(facing,shirt);obs.append(facing)
 for pts in cuffs:obs.append(fur_loop('Ivory sleeve cuffs',pts,.013,shirt))
 # Female top tucks into the skirt; a bulky coat-hem roll intersects the waistband.
 if not FEMALE:
  for pts in hems:obs.append(fur_loop('Ivory coat hem',pts,.012,shirt))
 # Front fastening strip follows the actual fitted garment surface.
 tree=BVHTree.FromPolygons([v.co for v in shirt.data.vertices],[list(f.vertices) for f in shirt.data.polygons])
 if not FEMALE:
  pts=[]
  for i in range(23):
   z=waist+.01+(neck-.056-waist)*i/22;hit,_,_,_=tree.ray_cast(Vector((0,-.5,z)),Vector((0,1,0)),1);pts.append(hit+Vector((0,-.006,0)) if hit else front(0,z,.024))
  strip=tube('Ivory coat placket',pts,.010,'fur',sides=6);follow_surface(strip,shirt);obs.append(strip)
 # Belt lives on the upperbody so it remains complete when lowerbody is swapped.
 SHIRT_REF=shirt
 z=waist+.067;rows=[]
 for dz in [-.025,0,.025]:
  row=[]
  for j in range(64):
   a=j*math.tau/64;d=Vector((math.sin(a),-math.cos(a),0));c=Vector((0,.02,z+dz));hit,_,_,_=tree.ray_cast(c+d*.5,-d,.8);row.append((hit if hit else ray(z+dz,a,.02))+d*.008)
  rows.append(row)
 beltob=ringmesh('Black Santa belt',rows,'black');follow_surface(beltob,shirt);thick(beltob,.004);obs.append(beltob)
 y=rows[1][0].y-.007
 for x,zz,w,hh in [(0,z+.026,.066,.008),(0,z-.026,.066,.008),(-.033,z,.008,.06),(.033,z,.008,.06)]:
  buckle=cube('Brass belt buckle',(x,y,zz),(w,.014,hh),'gold',None,.002);follow_surface(buckle,shirt);obs.append(buckle)
 return join(obs,SEX+'_Santa_Upperbody')

def lower_santa():
 waist=h('Hips').z+.04
 if not FEMALE:
  ob=slice_shell('Cotton trousers',.12,waist+.004,.32,.012,'red',.18,False);fit_surface(ob,.009)
  # The trousers are a complete independent garment. Keep the calves outside
  # the skin rather than shrinking them inside the legs to fit the boots.
  for side,sign in [('Left',1),('Right',-1)]:
   legtree=BVHTree.FromPolygons([v.co for v in BODY.data.vertices],[list(f.vertices) for f in BODY.data.polygons if all(BODY.data.vertices[i].co.x*sign>0 for i in f.vertices)])
   a=h(side+'Leg');b=h(side+'Foot')
   for v in ob.data.vertices:
    if v.co.x*sign<=0 or v.co.z>.47:continue
    c=b.lerp(a,(v.co.z-b.z)/(a.z-b.z));c.z=v.co.z;d=v.co-c;d.z=0
    if d.length<.0001:continue
    d.normalize();hit,_,_,_=legtree.ray_cast(c+d*.24,-d,.24)
    if hit is not None:
     radius=(hit-c).length+.010
     if (v.co-c).length<radius:v.co=c+d*radius
  thick(ob,.0025)
  return join([ob],SEX+'_Santa_Lowerbody')
 # Short flared skirt with a continuous hem, skin weights blend across the centre.
 n=64;nr=15;length=.32;rows=[]
 for i in range(nr):
  t=i/(nr-1);z=waist+.004-length*t
  row=[]
  for j in range(n):
   a=j*math.tau/n;p=cloth_outline(z,a,.031+.060*t*t)
   # Soft scalloped folds, large enough to read at the game camera distance.
   d=Vector((math.sin(a),-math.cos(a),0));p+=d*(.003*t*math.cos(a*12));row.append(p)
  rows.append(row)
 skirt=ringmesh('Flared Santa skirt',rows,'red');thick(skirt,.003);obs=[skirt]
 obs.append(fur_loop('Ivory skirt hem',rows[-1],.018,skirt))
 # Built-in fitted shorts keep the modular skirt covered during athletic poses.
 shorts=slice_shell('Cotton trousers',waist-.20,waist+.004,.32,.008,'black',.16,False);fit_surface(shorts,.007);thick(shorts,.002);obs.append(shorts)
 return join(obs,SEX+'_Santa_Lowerbody')

def gloves_santa():
 # Reuse the proven anatomical glove foundation, removing Halloween ornaments.
 before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(P/f'equipment/Rework/Pumpkin/{SEX}/Gloves.glb'))
 imported=list(set(bpy.data.objects)-before);ob=next(o for o in imported if o.type=='MESH' and 'Pumpkin' in o.name);world=ob.matrix_world.copy();ob.data.transform(world);ob.parent=None;ob.matrix_world=Matrix.Identity(4)
 # Preserve only the fitted leather hand surface; exclude decorative cuff bands.
 mats=[m.name for m in ob.data.materials];keep=[i for i,m in enumerate(mats) if m.split('.')[0]=='leather']
 bm=bmesh.new();bm.from_mesh(ob.data)
 if keep:bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.material_index not in keep],context='FACES')
 bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS');bm.to_mesh(ob.data);bm.free()
 ob.data.materials.clear();ob.data.materials.append(M['black'])
 for f in ob.data.polygons:f.material_index=0
 for a in list(ob.data.color_attributes):ob.data.color_attributes.remove(a)
 ob.modifiers.clear();ob.modifiers.new('Rework skeleton','ARMATURE').object=ARM;ob.parent=ARM;ob.matrix_parent_inverse=ARM.matrix_world.inverted()
 for o in imported:
  if o!=ob:bpy.data.objects.remove(o,do_unlink=True)
 ob.name=SEX+'_Santa_Gloves';return ob

def repair_boot_soles(ob):
 # The inherited toe/vamp shells extended below the old outsole. Identify
 # the two outsole components, then give each a supported, lower tread.
 bm=bmesh.new();bm.from_mesh(ob.data);seen=set();soles=[];uppers=[]
 for v in bm.verts:
  if v in seen:continue
  todo=[v];seen.add(v);vs=[]
  while todo:
   q=todo.pop();vs.append(q)
   for e in q.link_edges:
    w=e.other_vert(q)
    if w not in seen:seen.add(w);todo.append(w)
  if min(v.co.z for v in vs)<0 and max(v.co.z for v in vs)<.04:soles.extend(vs)
  else:uppers.extend(vs)
 assert soles,'Expected the anatomical boot outsole components'
 for v in uppers:
  if v.co.z<.010:v.co.z=.010
 for v in soles:
  if v.co.z<.005:v.co.z=-.019
 edges=list({e for v in soles for e in v.link_edges})
 # Subdivision supplies interior support for toe flex instead of long sole fans.
 bmesh.ops.subdivide_edges(bm,edges=edges,cuts=3,use_grid_fill=True)
 bmesh.ops.triangulate(bm,faces=list(bm.faces));bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(ob.data);bm.free();ob.data.update()
 # Sample one plantar weight field for every foot layer at the same XY.
 # This makes the vamp, toe underside, and sole bend consistently.
 for v in ob.data.vertices:
  if v.co.z>=.14:continue
  q=Vector((v.co.x,v.co.y,.025));hit,normal,idx,dist=TREE.find_nearest(q);corners=list(BODY.data.polygons[idx].vertices)[:3]
  bary=barycentric_transform(hit,*[BODY.data.vertices[k].co for k in corners],Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)))
  target={}
  for vi,fac in zip(corners,bary):
   for g in BODY.data.vertices[vi].groups:
    name=BODY.vertex_groups[g.group].name;target[name]=target.get(name,0)+g.weight*max(0,fac)
  alpha=max(0,min(1,(.14-v.co.z)/.06));old={ob.vertex_groups[g.group].name:g.weight for g in v.groups};weights={n:old.get(n,0)*(1-alpha)+target.get(n,0)*alpha for n in set(old)|set(target)}
  best=sorted(weights.items(),key=lambda x:-x[1])[:4];total=sum(w for n,w in best)
  for g in ob.vertex_groups:g.remove([v.index])
  for n,w in best:
   if w>0:(ob.vertex_groups.get(n) or ob.vertex_groups.new(name=n)).add([v.index],w/total,'REPLACE')
 normals(ob)

def boots_santa():
 # The existing anatomical boots supply a closed toe, sole and calf surface.
 before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=str(P/f'equipment/Rework/Pumpkin/{SEX}/Boots.glb'))
 imported=list(set(bpy.data.objects)-before);ob=next(o for o in imported if o.type=='MESH' and 'Pumpkin' in o.name);world=ob.matrix_world.copy();ob.data.transform(world);ob.parent=None;ob.matrix_world=Matrix.Identity(4)
 # Keep sole and leather only, discard orange piping, crossed straps and metal badges.
 names=[m.name for m in ob.data.materials];keep=[i for i,m in enumerate(names) if m.split('.')[0] in ['cloth','leather','dark']]
 bm=bmesh.new();bm.from_mesh(ob.data)
 if keep:bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.material_index not in keep or (names[f.material_index].split('.')[0]=='leather' and f.calc_center_median().z>.24)],context='FACES')
 bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS');bm.to_mesh(ob.data);bm.free()
 ob.data.materials.clear();ob.data.materials.append(M['black'])
 for f in ob.data.polygons:f.material_index=0;f.use_smooth=True
 for a in list(ob.data.color_attributes):ob.data.color_attributes.remove(a)
 ob.modifiers.clear();ob.modifiers.new('Rework skeleton','ARMATURE').object=ARM;ob.parent=ARM;ob.matrix_parent_inverse=ARM.matrix_world.inverted()
 for o in imported:
  if o!=ob:bpy.data.objects.remove(o,do_unlink=True)
 repair_boot_soles(ob)
 # Replace pointed crown with a level cuff by discarding top geometry and fitting roll.
 print('BOOT_PRE_CLIP',SEX, len(ob.data.vertices), [(min(v.co[i] for v in ob.data.vertices),max(v.co[i] for v in ob.data.vertices)) for i in range(3)],names,keep,flush=True)
 clip_surface(ob,lambda p:.453-p.z)
 if not FEMALE:
  pants=bpy.data.objects[SEX+'_Santa_Lowerbody']
  # Give the boot shaft enough room for the correctly fitted independent pants.
  for side,sign in [('Left',1),('Right',-1)]:
   panttree=BVHTree.FromPolygons([v.co for v in pants.data.vertices],[list(f.vertices) for f in pants.data.polygons if all(pants.data.vertices[i].co.x*sign>0 for i in f.vertices)])
   a=h(side+'Leg');b=h(side+'Foot')
   for v in ob.data.vertices:
    if v.co.x*sign<=0 or not .035<=v.co.z<=.453:continue
    c=b.lerp(a,(v.co.z-b.z)/(a.z-b.z));c.z=v.co.z;d=v.co-c;d.z=0
    if d.length<.0001:continue
    d.normalize();probe=c.copy();probe.z=max(.14,v.co.z);hit,_,_,_=panttree.ray_cast(probe+d*.26,-d,.26)
    if hit is not None:
     hit.z=v.co.z
     radius=(hit-c).length+.009+.009*max(0,min(1,(.28-v.co.z)/.10))
     if (v.co-c).length<radius:v.co=c+d*radius
  normals(ob)
 obs=[ob]
 for side in ['Left','Right']:
  a=h(side+'Leg');b=h(side+'Foot');z=.446;c=b.lerp(a,(z-b.z)/(a.z-b.z));pts=[]
  sign=1 if side=='Left' else -1
  tree=BVHTree.FromPolygons([v.co for v in ob.data.vertices],[list(f.vertices) for f in ob.data.polygons if all(ob.data.vertices[i].co.x*sign>0 for i in f.vertices)])
  for j in range(32):
   ang=j*math.tau/32;d=Vector((math.sin(ang),-math.cos(ang),0));hit,_,_,_=tree.ray_cast(c+d*.2,-d,.4);pts.append((hit if hit else c+d*.073)+d*.003)
  obs.append(fur_loop('Ivory boot cuff',pts,.013,ob))
 return join(obs,SEX+'_Santa_Boots')

def hat_santa():
 z=1.711 if FEMALE else 1.721;cy=.024 if FEMALE else .014;rx=.107 if FEMALE else .116;ry=.121 if FEMALE else .128
 n=32;rows=[]
 # A bent tapered cap with the tip and pom-pom falling to the wearer's right.
 for x,zz,s in [(0,z,1),(0,z+.060,.99),(.006,z+.133,.82),(.037,z+.204,.58),(.089,z+.237,.35),(.140,z+.206,.18),(.158,z+.166,.035)]:
  rows.append([Vector((x+rx*s*math.sin(j*math.tau/n),cy-ry*s*math.cos(j*math.tau/n),zz)) for j in range(n)])
 cap=ringmesh('Bent red Santa cap',rows,'red','Head');thick(cap,.002);obs=[cap]
 pts=[Vector((rx*math.sin(j*math.tau/48),cy-ry*math.cos(j*math.tau/48),z+.017)) for j in range(48)]
 cuff=tube('Ivory hat brim',pts+[pts[0]],.023,'fur','Head',8);obs.append(cuff)
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=.035,location=(.158,cy,z+.157));pom=bpy.context.object;pom.name='Ivory pom pom';active(pom);bpy.ops.object.transform_apply(location=True,rotation=False,scale=True);pom.data.materials.append(M['fur']);bind(pom,'Head');obs.append(pom)
 hat=join(obs,SEX+'_Santa_Hat')
 # Tailor the lowered crown and rolled brim to the actual skull section.
 # Radial clearance also accounts for the head's faceted silhouette.
 headtree=BVHTree.FromPolygons([v.co for v in BODY.data.vertices],[list(f.vertices) for f in BODY.data.polygons if min(BODY.data.vertices[i].co.z for i in f.vertices)>1.54])
 for v in hat.data.vertices:
  if v.co.z>1.90:continue
  c=Vector((0,cy,v.co.z));d=v.co-c;d.z=0
  if d.length<.0001:continue
  d.normalize();hit,_,_,_=headtree.ray_cast(c+d*.35,-d,.35)
  if hit is not None:
   radius=(hit-c).length+.009
   if (v.co-c).length<radius:v.co=c+d*radius
 normals(hat)
 return hat

def vertex_palette(ob):
 # One opaque rough material + vertex colours: a single batch per wearable.
 cols=ob.data.color_attributes.new(name='Color',type='BYTE_COLOR',domain='CORNER')
 for f in ob.data.polygons:
  color=ob.data.materials[f.material_index].diffuse_color
  for li in f.loop_indices:cols.data[li].color=color
 ob.data.materials.clear();ob.data.materials.append(PALETTE)
 for f in ob.data.polygons:f.material_index=0
 for uv in list(ob.data.uv_layers):ob.data.uv_layers.remove(uv)

report={}
for SEX in ['Male','Female']:
 FEMALE=SEX=='Female';bpy.ops.wm.read_factory_settings(use_empty=True)
 bpy.ops.import_scene.gltf(filepath=str(P/'appearance'/'v6'/'Models'/f'Base{SEX}_Appearance.glb'))
 BODY=next(o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith('Base'+SEX));ARM=next(m.object for m in BODY.modifiers if m.type=='ARMATURE')
 for o in list(bpy.data.objects):
  if o not in [BODY,ARM] and o.type=='MESH':bpy.data.objects.remove(o,do_unlink=True)
 bpy.context.view_layer.update();W=BODY.matrix_world.copy();BODY.data.transform(W);BODY.parent=None;BODY.matrix_world=Matrix.Identity(4);BODY.parent=ARM;BODY.matrix_parent_inverse=ARM.matrix_world.inverted();BODY.matrix_basis=Matrix.Identity(4);bpy.context.view_layer.update()
 TREE=BVHTree.FromPolygons([v.co for v in BODY.data.vertices],[list(f.vertices) for f in BODY.data.polygons])
 CLEAN=BODY.copy();CLEAN.data=BODY.data.copy();bpy.context.collection.objects.link(CLEAN);CLEAN.name='Garment foundation';CLEAN.modifiers.clear();active(CLEAN)
 bm=bmesh.new();bm.from_mesh(CLEAN.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0001);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(CLEAN.data);bm.free()
 if CLEAN.data.has_custom_normals:bpy.ops.mesh.customdata_custom_splitnormals_clear()
 md=CLEAN.modifiers.new('Unified cloth surface','REMESH');md.mode='VOXEL';md.voxel_size=.012;bpy.ops.object.modifier_apply(modifier=md.name)
 md=CLEAN.modifiers.new('Soft cloth surface','SMOOTH');md.factor=.7;md.iterations=3;bpy.ops.object.modifier_apply(modifier=md.name)
 CLEAN.vertex_groups.clear();bind(CLEAN);CLEAN.hide_render=True;CLEAN.hide_set(True)
 M={k:material('Santa '+k,c) for k,c in {'red':(.42,.003,.010),'fur':(.9,.85,.74),'black':(.012,.016,.021),'gold':(.64,.36,.075)}.items()}
 PALETTE=material('Santa palette',(.8,.8,.8));node=PALETTE.node_tree.nodes.new('ShaderNodeVertexColor');node.layer_name='Color';PALETTE.node_tree.links.new(node.outputs['Color'],PALETTE.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
 pieces={'Hat':hat_santa(),'Upperbody':upper_santa(),'Lowerbody':lower_santa(),'Gloves':gloves_santa(),'Boots':boots_santa()}
 report[SEX]={}
 for key,ob in pieces.items():
  vertex_palette(ob);ob.data.calc_loop_triangles();vs=[v.co for v in ob.data.vertices]
  bones=sorted({ob.vertex_groups[g.group].name.replace(':','') for v in ob.data.vertices for g in v.groups if g.weight>0})
  report[SEX][key]={'triangles':len(ob.data.loop_triangles),'vertices':len(vs),'material_batches':1,'texture_images':0,'bones':bones,'bounds':[[min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]]}
  active(ob);ARM.select_set(True);bpy.ops.export_scene.gltf(filepath=str(OUT/SEX/(key+'.glb')),export_format='GLB',use_selection=True,export_animations=False)
 BODY.hide_set(False);BODY.hide_render=False
 bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Source'/f'{SEX}_Santa.blend'))
 print('BUILT',SEX,{k:v['triangles'] for k,v in report[SEX].items()},flush=True)
(OUT/'geometry_report.json').write_text(json.dumps(report,indent=2))
