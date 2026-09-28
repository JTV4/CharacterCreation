"""Fitted, opaque, head-skinned facial hair. Run with Blender 4.1+ --background --python."""
import bpy, math, sys, argparse, random
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
parser=argparse.ArgumentParser();parser.add_argument('--base-models',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--render',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.output
for d in ['Models','Sources','Previews']:(out/d).mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(args.base_models/'BaseMale_Appearance.glb'))
s=bpy.context.scene
for o in list(s.objects):
 if o.name.startswith('Icosphere'):bpy.data.objects.remove(o,do_unlink=True)
body=next(o for o in s.objects if o.type=='MESH' and 'Rework' in o.name);rig=next(o for o in s.objects if o.type=='ARMATURE');rig.animation_data_clear()
for b in rig.pose.bones:b.matrix_basis=Matrix.Identity(4)
bpy.context.view_layer.update()
vs=[body.matrix_world@v.co for v in body.data.vertices];bvh=BVHTree.FromPolygons(vs,[list(f.vertices) for f in body.data.polygons if all(vs[i].z>1.45 for i in f.vertices)])
mat=bpy.data.materials.new('GS_FacialHair');mat.use_nodes=True;bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.9
vc=mat.node_tree.nodes.new('ShaderNodeVertexColor');vc.layer_name='Color';mat.node_tree.links.new(vc.outputs['Color'],bs.inputs['Base Color'])
def interp(a,knots):
 for (u,x),(v,y) in zip(knots,knots[1:]):
  if a<=v:return x+(y-x)*max(0,(a-u)/(v-u))
 return knots[-1][1]
def bounds(a):
 a=abs(a)
 return interp(a,[(0,1.585),(.24,1.577),(.55,1.603),(.9,1.622),(1.25,1.636),(1.46,1.653)]),interp(a,[(0,1.543),(.4,1.547),(.8,1.566),(1.2,1.588),(1.46,1.610)])
def surface(a,z,lift=0):
 d=Vector((math.sin(a),-math.cos(a),0));origin=Vector((0,.025,z));hit,normal,_,_=bvh.ray_cast(origin+d*.3,-d)
 if hit is None:raise ValueError(('surface miss',a,z))
 return hit+d*lift

def face(x,z,lift=.002):
 hit,_,_,_=bvh.ray_cast(Vector((x,-.3,z)),Vector((0,1,0)))
 if hit is None:raise ValueError(('face miss',x,z))
 return hit+Vector((0,-lift,0))
class Mesh:
 def __init__(self):self.v=[];self.f=[];self.c=[];self.embedded=set()
 def vertex(self,p,c=.8):self.v.append(Vector(p));self.c.append(c);return len(self.v)-1
 def tube(self,pts,widths,depths=None,shade=.86,sides=6,attach_count=0):
  pts=list(map(Vector,pts));depths=depths or widths;start=len(self.v)
  for i,p in enumerate(pts):
   tangent=(pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)]).normalized();a=tangent.cross(Vector((0,-1,0))).normalized();b=a.cross(tangent).normalized()
   for j in range(sides):
    t=j*math.tau/sides;q=p+a*math.cos(t)*widths[i]+b*math.sin(t)*depths[i]
    if i<attach_count:
     # Shape each root ring against the faceted lip, with its back embedded.
     # A fixed forward offset leaves the entire pencil mustache floating.
     depth=depths[i]+p.y-q.y-.00035
     q.y=face(q.x,q.z,0).y-depth
    self.vertex(q,shade*(.86+.14*max(0,math.sin(t))))
  for i in range(len(pts)-1):
   for j in range(sides):a=start+i*sides+j;b=start+i*sides+(j+1)%sides;self.f.append((a,a+sides,b+sides,b))
  self.f.append(tuple(start+j for j in reversed(range(sides))));self.f.append(tuple(start+(len(pts)-1)*sides+j for j in range(sides)))
 def beard(self,style):
  # MMORPG-inspired sculpted masses: broad overlapping locks, dark roots,
  # staggered tips and restrained asymmetry. Mustaches remain separate meshes.
  rng=random.Random(804+sum(map(ord,style)))
  small=style in ['goatee','braided','soul_patch']
  extent={'goatee':.28,'braided':.36,'soul_patch':.085}.get(style,1.42)
  length={'full':.028,'ducktail':.051,'rounded_full':.038,'goatee':.009,'braided':.008,'forked':.043}.get(style,0)
  volume={'full':.009,'ducktail':.009,'rounded_full':.014,'goatee':.004,'braided':.005,'mutton_chops':.006,'forked':.009}.get(style,.0025)
  def smooth(a,knots):
   for (u,x),(v,y) in zip(knots,knots[1:]):
    if a<=v:
     f=max(0,min(1,(a-u)/(v-u)));f=f*f*(3-2*f);return x+(y-x)*f
   return knots[-1][1]
  def profile(a):
   aa=abs(a)
   top=smooth(aa,[(0,1.584),(.18,1.579),(.37,1.589),(.55,1.600),(.86,1.614),(1.17,1.627),(1.42,1.650)])
   _,base=bounds(a)
   if style=='chin_strap':top=base+.011+.026*(aa/extent)**5
   if small:top=1.582-.008*(aa/extent)**1.5
   if style=='soul_patch':top=1.585;base=1.573
   return top,base
  def point(a,t,extra=0):
   st=max(0,min(1,t));top,base=profile(a)
   # Broken, shallow root line; no thick rim on the cheek.
   top+=.0006*math.sin(a*53+.5)+.00035*math.sin(a*97)
   z=top+(base-top)*st
   aa=a
   if small:aa*=1-(.85 if style=='soul_patch' else .30)*st**2
   q=surface(aa,max(z,base+.008),.00025+volume*math.sin(st*math.pi*.82)+extra)
   q.z=z
   front=max(0,math.cos(a))
   drop=length*front**2
   if style=='ducktail':drop=length*front**3;q.x*=1-.27*st**3*front**2
   if style=='rounded_full':drop=length*front**.75;q.x+=math.sin(a)*.009*math.sin(st*math.pi)*front
   if style=='forked':drop=(.008+.043*math.exp(-((abs(a)-.28)/.21)**2))*front**2
   q.z-=drop*st**1.7
   if length:q.y-=.004*st**2*front
   if t<0:q.z-=t*.024
   if t>1:q.z-=(t-1)*(.030 if length else .016)
   return q
  domains=[(-extent,-.53),(.53,extent)] if style=='mutton_chops' else [(-extent,extent)]
  if style=='stubble':
   # Dense, tiny opaque strokes instead of large scattered dots.
   for j in range(105):
    a=-extent+2*extent*(j+rng.random())/105
    for k in range(17):
     t=(k+rng.random())/17;q=point(a,t,.0004);tangent=Vector((math.cos(a),math.sin(a),0))
     w=rng.uniform(.00028,.00047);height=rng.uniform(.0008,.0015)
     ids=[self.vertex(v,rng.uniform(.57,.80)) for v in [q-tangent*w,q+tangent*w,q+Vector((0,0,-height))]];self.f.append(tuple(reversed(ids)))
   return
  for lo,hi in domains:
   n=17 if small else (23 if style=='mutton_chops' else 53);r=9;start=len(self.v)
   for j in range(n):
    a=lo+(hi-lo)*j/(n-1)
    for k in range(r):
     t=k/(r-1)*.965
     shade=.60+.12*math.sin(t*math.pi)+.045*math.sin(a*19+t*4)
     self.vertex(point(a,t),shade)
   for j in range(n-1):
    for k in range(r-1):i=start+j*r+k;self.f.append((i,i+1,i+r+1,i+r))
   # Concealed inward skirts at underside and sideburns.
   edge=[start+j*r for j in range(n)]+[start+(n-1)*r+k for k in range(1,r)]+[start+j*r+r-1 for j in reversed(range(n-1))]+[start+k for k in reversed(range(1,r-1))]
   inset=[]
   for idx in edge:
    q=self.v[idx];normal=Vector((q.x,q.y-.025,0)).normalized();inset.append(self.vertex(q-normal*.0025,.55));self.embedded.add(inset[-1])
   for i in range(len(edge)):j=(i+1)%len(edge);self.f.append((edge[i],inset[i],inset[j],edge[j]))
   # A lock is a broad, low convex surface tapering to an irregular tip.
   # Surface sampling keeps roots attached even on the angular cheek mesh.
   def lock(a,t0,t1,width,seed):
    rnd=random.Random(seed);start=len(self.v);segments=5;cross=5
    bend=rnd.uniform(-.06,.06);shade=rnd.uniform(.75,.89)
    for k in range(segments):
     u=k/(segments-1);t=t0+(t1-t0)*u
     taper=[.55,1,.89,.58,.015][k]
     center=a+bend*u**1.5
     for j in range(cross):
      x=-1+2*j/(cross-1);angle=max(lo+.0001,min(hi-.0001,center+x*width*taper))
      bulge=max(0,1-x*x)*math.sin(u*math.pi*.90)*(.00065 if t1<.2 else (.0026 if length else .0013))
      q=point(angle,t,.00025+bulge)
      # Painted-style light on the broad planes, shadow in the overlaps.
      c=shade*(.80+.20*(1-x*x))*(.89+.11*math.sin(u*math.pi))
      self.vertex(q,c)
    for k in range(segments-1):
     for j in range(cross-1):i=start+k*cross+j;self.f.append((i,i+cross,i+cross+1,i+1))
   count=5 if style=='soul_patch' else (9 if small else (10 if style=='mutton_chops' else 17))
   rows=[(0,.67),(.33,1.07)] if length else [(0,1.06)]
   if style=='soul_patch':rows=[(0,1.04)]
   for row,(t0,t1) in enumerate(rows):
    spacing=(hi-lo)/count
    for j in range(count):
     a=lo+spacing*(j+.5+(.22 if row%2 else 0))
     if a>=hi:continue
     a+=rng.uniform(-.14,.14)*spacing
     lock(a,max(0,t0+rng.uniform(-.04,.04)),t1+rng.uniform(-.055,.055),spacing*rng.uniform(.56,.77),rng.randrange(100000))
   # Fine root tufts break the cheek edge without transparency or textures.
   for j in range(count*2):
    a=lo+(hi-lo)*(j+.5)/(count*2);lock(a,-.025,.16,(hi-lo)/(count*2)*.30,j+810)
  if style=='braided':
   root=point(0,1.0);root.z+=.003
   # Three interwoven tapered strands, with a tucked ending and a narrow tie.
   for strand in range(3):
    pts=[];ws=[]
    for k in range(49):
     t=k/48;ang=t*math.tau*3.5+strand*math.tau/3;radius=.008*(1-.62*t)
     pts.append(root+Vector((math.cos(ang)*radius,math.sin(ang)*radius-.003*t,-.084*t)))
     ws.append(.0048*(1-.60*t))
    self.tube(pts,ws,shade=[.76,.85,.94][strand],sides=6)
   end=root+Vector((0,-.003,-.081))
   ring=[end+Vector((math.cos(i*math.tau/12)*.005,math.sin(i*math.tau/12)*.005,0)) for i in range(13)]
   self.tube(ring,[.0018]*13,shade=.35)
   self.tube([end,end+Vector((0,0,-.011)),end+Vector((.002,0,-.020))],[.004,.0045,.0004],shade=.81)
 def extra_mustache(self,style):
  for sign in [-1,1]:
   pts=[];ws=[]
   length=.023 if style=='petite_handlebar' else .031
   for k in range(11):
    t=k/10;x=(.0003 if style=='walrus' else .0015)+length*t
    z=(1.601 if style=='walrus' else 1.604)-(.010 if style=='walrus' else .006)*t
    if style=='english':z=1.603-.003*t
    if style=='dali':z=1.603-.0015*math.sin(t*math.pi)
    w={'walrus':.0092,'imperial':.0058,'english':.0024,'dali':.0018,'petite_handlebar':.0031}[style]
    w*=(.8+.2*math.sin(math.pi*t*.86)) if style=='walrus' else (.5+.5*math.sin(math.pi*t*.86))
    if style=='walrus':w*=1-.35*t
    pts.append(face(sign*x,z,.004));ws.append(w)
   tips={
    'english':[(.039,1.600,.0018),(.047,1.601,.0012),(.058,1.603,.0002)],
    'dali':[(.037,1.607,.0015),(.043,1.618,.0013),(.046,1.630,.0009),(.046,1.640,.0002)],
    'imperial':[(.038,1.601,.0048),(.044,1.610,.0038),(.043,1.620,.0027),(.035,1.622,.0015),(.032,1.617,.0003)],
    'petite_handlebar':[(.029,1.598,.0025),(.034,1.603,.0021),(.033,1.609,.0014),(.028,1.610,.0003)],
    'walrus':[(.034,1.588,.0035),(.034,1.582,.0005)],
   }
   for x,z,w in tips[style]:pts.append(face(sign*x,z,.005));ws.append(w)
   ds=[w*(.6 if style=='walrus' else .8) for w in ws]
   for i in range(11):pts[i]=face(pts[i].x,pts[i].z,ds[i]-.00035)
   self.tube(pts,ws,ds,.84,sides=8,attach_count=11)
   for j in [-1,0,1]:
    ridge=[v+Vector((0,-ds[i]*.85,ws[i]*j*.45)) for i,v in enumerate(pts)]
    self.tube(ridge,[max(.00015,w*.12) for w in ws],shade=.92 if j==1 else .78,sides=4)
 def mustache(self,style):
  if style in ['walrus','english','dali','imperial','petite_handlebar']:return self.extra_mustache(style)
  for sign in [-1,1]:
   pts=[];ws=[];ds=[]
   for k in range(13):
    t=k/12;x=.002+.029*t
    z=1.605-.009*t**1.25
    if style=='pencil':z-=.0025
    q=face(sign*x,z,.003+.001*math.sin(t*math.pi));pts.append(q)
    w=(.0062 if style=='chevron' else .0036)*math.sin((.15+t*.85)*math.pi)
    if style=='pencil':w*=.45
    if style in ['handlebar','horseshoe']:w=.0034*(.4+.6*math.sin(math.pi*t*.85))
    ws.append(max(.0005,w));ds.append(max(.0005,w*.64))
   if style=='handlebar':
    for x,z,w in [(.035,1.595,.0028),(.041,1.599,.0026),(.045,1.606,.002),(.043,1.611,.0012),(.039,1.612,.0003)]:pts.append(face(sign*x,z,.006));ws.append(w);ds.append(w*.75)
   elif style=='horseshoe':
    for x,z,w in [(.031,1.590,.0038),(.030,1.581,.0035),(.029,1.572,.003),(.028,1.566,.0006)]:pts.append(face(sign*x,z,.003));ws.append(w);ds.append(w*.7)
   for i in range(13):pts[i]=face(pts[i].x,pts[i].z,ds[i]-.00035)
   self.tube(pts,ws,ds,.86,sides=8,attach_count=13)
   for j in [-1,1]:
    ridge=[v+Vector((0,-ds[i]*.83,ws[i]*j*.35)) for i,v in enumerate(pts)]
    self.tube(ridge,[max(.00015,w*.15) for w in ws],shade=.94 if j==1 else .72,sides=4)
 def export(self,name):
  if '_Beard_' in name:
   def deficit(p):
    if p.z<1.544:return 0
    normal=Vector((p.x,p.y-.025,0));radius=normal.length
    if radius<.01:return 0
    normal.normalize();origin=Vector((0,.025,p.z));hit,_,_,_=bvh.ray_cast(origin+normal*.3,-normal)
    if hit is None:return 0
    return max(0,(hit-origin).length+.00025-radius)
   remaining=[.0025]*len(self.v)
   for _ in range(4):
    moves=[0 if i in self.embedded else deficit(p) for i,p in enumerate(self.v)]
    for face_ids in self.f:
     if any(i in self.embedded for i in face_ids):continue
     d=deficit(sum((self.v[i] for i in face_ids),Vector())/len(face_ids))
     if d:
      for i in face_ids:moves[i]=max(moves[i],d*1.1)
    if max(moves,default=0)<.0001:break
    for i,d in enumerate(moves):
     d=min(d,remaining[i]);remaining[i]-=d
     if d:self.v[i]+=Vector((self.v[i].x,self.v[i].y-.025,0)).normalized()*d
  bpy.ops.object.select_all(action='DESELECT');me=bpy.data.meshes.new(name);me.from_pydata(self.v,[],self.f);me.update();o=bpy.data.objects.new(name,me);s.collection.objects.link(o);me.materials.append(mat)
  for f in me.polygons:f.use_smooth=True
  bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.normals_make_consistent(inside=False);bpy.ops.object.mode_set(mode='OBJECT')
  attr=me.color_attributes.new(name='Color',type='BYTE_COLOR',domain='POINT');me.color_attributes.active_color=attr
  for i,c in enumerate(self.c):attr.data[i].color=(c,c,c,1)
  o.parent=rig;o.matrix_world=Matrix.Identity(4);o.modifiers.new('Head skin','ARMATURE').object=rig;o.vertex_groups.new(name='mixamorig:Head').add(list(range(len(self.v))),1,'REPLACE')
  rig.select_set(True);bpy.context.view_layer.objects.active=rig
  bpy.ops.export_scene.gltf(filepath=str(out/'Models'/f'{name}.glb'),use_selection=True,export_format='GLB',export_animations=False,export_cameras=False,export_lights=False)
  return o

def aim(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
s.render.engine='BLENDER_EEVEE';s.eevee.use_gtao=True;s.eevee.gtao_distance=.04;s.eevee.gtao_factor=1.1;s.eevee.taa_render_samples=32;s.world=bpy.data.worlds.new('Studio');s.world.color=(.1,.1,.1);s.view_settings.view_transform='AgX'
for loc,power in [((1,-2,3),100),((-2,-1,2),65),((0,2,2.6),100)]:
 d=bpy.data.lights.new('Softbox','AREA');d.energy=power;d.size=2;o=bpy.data.objects.new('Softbox',d);s.collection.objects.link(o);o.location=loc;aim(o,(0,0,1.64))
d=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',d);s.collection.objects.link(cam);s.camera=cam;d.type='ORTHO';d.ortho_scale=.36
s.render.resolution_x=480;s.render.resolution_y=560;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.film_transparent=True
for kind,styles in [('Beard',['stubble','short_boxed','full','goatee','chin_strap','braided','ducktail','rounded_full','mutton_chops','soul_patch','forked']),('Mustache',['natural','pencil','chevron','handlebar','horseshoe','walrus','english','dali','imperial','petite_handlebar'])]:
 for style in styles:
  m=Mesh();getattr(m,kind.lower())(style);o=m.export(f'Male_{kind}_{style}')
  if args.render:
   mix=mat.node_tree.nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1;mix.inputs[2].default_value=(.12,.047,.023,1);mat.node_tree.links.new(vc.outputs['Color'],mix.inputs[1]);mat.node_tree.links.new(mix.outputs[0],bs.inputs['Base Color'])
   for label,loc in [('front',(.22,-1,1.74)),('side',(.85,-.65,1.72))]:
    cam.location=loc;aim(cam,(0,-.015,1.62));s.render.filepath=str(out/'Previews'/f'{kind}_{style}_{label}.png');bpy.ops.render.render(write_still=True)
   mat.node_tree.nodes.remove(mix);mat.node_tree.links.new(vc.outputs['Color'],bs.inputs['Base Color'])
  o.hide_render=True;o.hide_set(True)
for name in ['Male_Beard_short_boxed','Male_Mustache_natural']:
 o=bpy.data.objects[name];o.hide_render=False;o.hide_set(False)
bpy.ops.wm.save_as_mainfile(filepath=str(out/'Sources'/'Male_Facial_Hair.blend'),compress=True)
