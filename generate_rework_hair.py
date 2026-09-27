"""Reproducible fitted hair assets. Blender 4.1+, no add-ons or textures required."""
import bpy, math, json, sys, random, argparse
from functools import lru_cache
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
parser=argparse.ArgumentParser()
parser.add_argument('--base-models',type=Path,default=Path.cwd()/'viewer/public/appearance/v6/Models')
parser.add_argument('--output',type=Path,default=Path.cwd()/'rework_hair')
parser.add_argument('--sex',choices=['Male','Female'])
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
CC=args.base_models.resolve();OUT=args.output.resolve()
STYLES={'Female':['ponytail','bun','short','long','french_braid'],'Male':['mullet','mohawk','buzz_cut','ponytail','short','shaggy','dreads']}
for p in ['Models','Previews','Sources']: (OUT/p).mkdir(parents=True,exist_ok=True)
TAU=2*math.pi

def aim(obj,p):obj.rotation_euler=(Vector(p)-obj.location).to_track_quat('-Z','Y').to_euler()
def setup_scene(sex):
 bpy.ops.wm.read_factory_settings(use_empty=True)
 bpy.ops.import_scene.gltf(filepath=str(CC/f'Base{sex}_Appearance.glb'))
 s=bpy.context.scene
 for o in list(s.objects):
  if o.name.startswith('Icosphere'):bpy.data.objects.remove(o,do_unlink=True)
 body=next(o for o in s.objects if o.type=='MESH' and 'Rework' in o.name)
 rig=next(o for o in s.objects if o.type=='ARMATURE')
 # Match the current, aligned runtime base, not the older authoring bind pose.
 rig.animation_data_clear()
 for b in rig.pose.bones:b.matrix_basis=Matrix.Identity(4)
 for mat in body.data.materials:
  if mat.name=='GS_Skin':
   bs=mat.node_tree.nodes.get('Principled BSDF')
   for link in list(bs.inputs['Base Color'].links):mat.node_tree.links.remove(link)
   bs.inputs['Base Color'].default_value=(.53,.32,.205,1);bs.inputs['Roughness'].default_value=.8
 center=Vector((0,.025,1.683 if sex=='Male' else 1.669))
 verts=[body.matrix_world@v.co for v in body.data.vertices]
 faces=[list(f.vertices) for f in body.data.polygons if all(verts[i].z>1.55 for i in f.vertices)]
 skull=BVHTree.FromPolygons(verts,faces)
 mat=bpy.data.materials.new('GS_Hair');mat.use_nodes=True
 bs=mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(1,1,1,1);bs.inputs['Roughness'].default_value=.86
 vc=mat.node_tree.nodes.new('ShaderNodeVertexColor');vc.name='HairColor';vc.layer_name='Color';mat.node_tree.links.new(vc.outputs['Color'],bs.inputs['Base Color'])
 s.render.engine='BLENDER_EEVEE';s.eevee.use_gtao=True;s.eevee.gtao_distance=.18;s.eevee.gtao_factor=1.22;s.eevee.taa_render_samples=48
 s.world=bpy.data.worlds.new('Studio');s.world.color=(.035,.035,.035);s.view_settings.view_transform='AgX'
 for name,loc,power,size in [('Key',(1,-2,3),95,2),('Fill',(-2,-1,2),55,2),('Rim',(0,2,2.6),120,1.5)]:
  d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size;o=bpy.data.objects.new(name,d);s.collection.objects.link(o);o.location=loc;aim(o,center)
 d=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',d);s.collection.objects.link(cam);s.camera=cam;d.type='ORTHO';d.ortho_scale=.64
 s.render.resolution_x=560;s.render.resolution_y=640;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.film_transparent=True
 return s,body,rig,center,skull,mat

class Hair:
 def __init__(self,center,skull,style,sex):self.v=[];self.f=[];self.c=[];self.center=center;self.skull=skull;self.style=style;self.sex=sex
 def vertex(self,p,c=.82):self.v.append(Vector(p));self.c.append(c);return len(self.v)-1
 def scalp(self,theta,phi,lift=.005):
  d=Vector((math.sin(phi)*math.sin(theta),-math.sin(phi)*math.cos(theta),math.cos(phi)))
  hit,_,_,_=self.skull.ray_cast(self.center+d*.35,-d)
  if hit is None or (hit-self.center).length>.20:hit=self.center+Vector((d.x*.083,d.y*.083,d.z*.106))
  return hit+d*lift
 @lru_cache(maxsize=512)
 def end(self,t):
  # Keep a level forehead, descend almost vertically at the temple, make
  # a small backward step, then descend again and turn back above the ear.
  # Dense boundary samples retain this redline profile after simplification.
  a=abs(math.atan2(math.sin(t),math.cos(t)))
  def previous(angle):
   front=max(0,math.cos(angle))
   return (2.12-.92*front-.47*abs(math.sin(angle))**8
     -.30*front**1.8
     -(.14 if self.sex=='Male' else .09)*math.exp(-((angle-.66)/.27)**2)*front
     +.025*math.exp(-(angle/.19)**2))
  if a>=1.85:return previous(a)
  front_z=self.scalp(0,previous(0),0).z
  ear_z=self.scalp(math.copysign(1.50,math.sin(t)),previous(1.50),0).z
  # Small style-dependent variation retains the same overall temple anatomy.
  variation={'short':.008,'mullet':.008,'buzz_cut':-.006,'mohawk':-.006,
             'shaggy':.012,'dreads':.012,'long':-.008}.get(self.style,0)
  a_side=a-variation if a>.80 else a
  if a<=1.50:
   knots=[(0,front_z),(.85,front_z),(.89,front_z-.001),
          (.985,front_z-.020),(1.025,front_z-.024),(1.08,front_z-.028),
          (1.11,ear_z+.006),(1.14,ear_z+.002),(1.48,ear_z+.001),(1.52,ear_z)]
   for (u,z0),(v,z1) in zip(knots,knots[1:]):
    if a_side<=v:
     q=max(0,min(1,(a_side-u)/(v-u)));target=z0+(z1-z0)*q;break
  else:
   u=(a-1.50)/.35
   original_z=self.scalp(t,previous(a),0).z
   target=ear_z*(1-u)+original_z*u
  # Submillimeter irregularity keeps the front from looking ruler-cut.
  target+=.00035*math.sin(t*9+.4)*max(0,1-a/1.85)
  lo=.2;hi=2.5
  for _ in range(18):
   mid=(lo+hi)*.5
   if self.scalp(t,mid,0).z>target:lo=mid
   else:hi=mid
  return (lo+hi)*.5
 def cap(self,buzz=False):
  angles=sorted(set([j*TAU/40 for j in range(40)]+[a for x in [.85,.89,.985,1.025,1.08,1.11,1.14,1.48] for a in [x,TAU-x]]))
  n=len(angles);r=16;start=len(self.v)
  for k in range(r):
   t=k/(r-1)
   for j in range(n):
    theta=angles[j];phi=.018+(self.end(theta)-.018)*t
    flow=theta+.18*(1-t)
    ridge=(.5+.5*math.cos(theta*24+phi*1.8))
    lift=(.0040 if buzz else .0060)+(.0004 if buzz else .0025)*ridge*math.sin(phi)
    if self.style in ['short','mullet','shaggy']:lift+=.009*max(0,math.cos(phi))
    edge=max(0,(t-.70)/.30)*max(0,math.cos(theta))**2
    lift=lift*(1-.55*edge)
    p=self.scalp(theta,phi,lift)
    shade=(.55+.10*random.Random(k*n+j).random()) if buzz else (.72+.14*ridge)
    self.vertex(p,shade)
  for k in range(r-1):
   for j in range(n):a=start+k*n+j;b=start+k*n+(j+1)%n;self.f.append((a,b,b+n,a+n))
  self.f.append(tuple(reversed([start+j for j in range(n)])))
  # A narrow inward rim avoids paper-thin exposed hairlines.
  rim=[]
  for j in range(n):
   p=self.v[start+(r-1)*n+j];rim.append(self.vertex(p-(p-self.center).normalized()*.002,.60))
  for j in range(n):a=start+(r-1)*n+j;b=start+(r-1)*n+(j+1)%n;self.f.append((a,rim[j],rim[(j+1)%n],b))
 def tube(self,points,widths,depths=None,sides=8,shade=.86,flatten=None,groove=0):
  pts=[Vector(p) for p in points];depths=depths or widths;start=len(self.v)
  for i,p in enumerate(pts):
   tangent=(pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)]).normalized()
   normal=Vector(flatten) if flatten else (p-self.center).normalized()
   a=tangent.cross(normal)
   if a.length<.05:a=tangent.cross(Vector((1,0,0)))
   if a.length<.05:a=tangent.cross(Vector((0,1,0)))
   a.normalize();b=a.cross(tangent).normalized()
   for j in range(sides):
    angle=j*TAU/sides;wave=1+groove*math.cos(angle*3+i*.3)
    self.vertex(p+a*(math.cos(angle)*widths[i]*wave)+b*(math.sin(angle)*depths[i]*wave),shade*(.86+.14*max(0,math.sin(angle))))
  for i in range(len(pts)-1):
   for j in range(sides):a=start+i*sides+j;b=start+i*sides+(j+1)%sides;self.f.append((a,a+sides,b+sides,b))
  self.f.append(tuple(start+j for j in reversed(range(sides))));self.f.append(tuple(start+(len(pts)-1)*sides+j for j in range(sides)))
 def flow(self,n=22,shag=False,short=False):
  for j in range(n):
   theta=j*TAU/n
   pts=[];ws=[];ds=[]
   for k in range(9):
    t=k/8;phi=.17+(self.end(theta)-.17)*t
    angle=theta+(.65 if short else .19)*(1-t)
    lift=.002+(.019 if short else .009)*math.sin(t*math.pi)
    p=self.scalp(angle,phi,lift)
    if shag and t>.64:
     drop=(.026+.027*(.5+.5*math.sin(j*2.6)))*(1-.66*max(0,math.cos(theta))**2)
     p.z-=drop*((t-.64)/.36);p+=(p-self.center).normalized()*.009*t
    if short and math.cos(theta)>.15:p.x+=.015*(1-t)*math.sin(t*math.pi);p.z+=.006*math.sin(t*math.pi)
    pts.append(p);ws.append((.019 if short else .015)*(.25+.75*math.sin(math.pi*t*.93))*(1 if t<.88 else .20));ds.append(.0035 if k<8 else .0008)
   self.tube(pts,ws,ds,8,.86+.06*math.sin(j*1.7))
 def tail(self,sex):
  z=self.center.z
  # Sculpted solid mass with longitudinal lobes, and separate tapered locks.
  pts=[(0,.098,z+.055),(0,.145,z+.06),(.004,.184,z+.015),(.016,.187,z-.06),(.028,.171,z-.15),(.035,.163,z-(.25 if sex=='Female' else .19))]
  self.tube(pts,[.019,.027,.036,.033,.023,.0018],[.019,.023,.026,.024,.017,.001],12,.89,flatten=(0,1,0),groove=.11)
  for j in range(7):
   a=j*TAU/7;points=[]
   for k,p in enumerate(pts):
    p=Vector(p);r=[.018,.025,.032,.029,.019,.002][k];p.x+=math.cos(a)*r;p.y+=math.sin(a)*r*.78;points.append(p)
   self.tube(points,[.003,.006,.007,.007,.006,.0006],[.002,.003,.003,.003,.002,.0004],6,.80+.07*math.cos(a),flatten=(0,1,0))
  # Woven tie is vertex shaded, still the same tintable material and draw call.
  ring=[(math.cos(a)*.023,.139+math.sin(a)*.023,z+.061) for a in [j*TAU/16 for j in range(17)]]
  self.tube(ring,[.0035]*17,sides=6,shade=.37,flatten=(0,1,0))
 def bun(self):
  z=self.center.z
  # Rounded core, with a continuous wrapped coil defining the bun silhouette.
  pts=[(0,.083,z+.065),(0,.101,z+.085),(0,.124,z+.087),(0,.147,z+.077),(0,.155,z+.068)]
  self.tube(pts,[.005,.035,.043,.030,.003],sides=16,shade=.82,flatten=(0,0,1))
  pts=[];ws=[]
  for i in range(65):
   t=i/64;a=t*TAU*2.5;r=.037*(1-.75*t)
   pts.append((math.cos(a)*r,.140+.017*math.sin(t*math.pi),z+.084+math.sin(a)*r));ws.append(.009*(1-.8*t))
  self.tube(pts,ws,sides=8,shade=.94,flatten=(0,1,0))
 def curtain(self,mullet=False):
  # Thick tapered panels, overlapping into an opaque back volume.
  count=13 if mullet else 21
  for j in range(count):
   theta=(1.47 if mullet else .91)+j/(count-1)*((TAU-2*1.47) if mullet else (TAU-2*.91))
   points=[];ws=[];ds=[]
   length=(.14 if mullet else .29)+.018*math.sin(j*1.8)
   for k in range(11):
    t=k/10
    if t<.46:p=self.scalp(theta+.13*(1-t),.3+1.22*t/.46,.01)
    else:
     q=(t-.46)/.54;p=self.scalp(theta,1.52,.012);p.z-=length*q;p.x+=math.sin(theta)*(.022*math.sin(q*math.pi)+.012*q);p.y+=max(.0,-math.cos(theta))*.019*q
     p.x+=.009*math.sin(q*TAU+j*.7)*q
    points.append(p);ws.append((.018 if mullet else .021)*(.5+.5*math.sin(t*math.pi))*(1 if t<.91 else .10));ds.append(.008 if t<.9 else .001)
   self.tube(points,ws,ds,8,.79+.10*(.5+.5*math.cos(j*2.3)))
 def slick(self):
  # Hairline-to-tie strokes run backwards, with no radial fringe around the face.
  target=Vector((0,.80,.60))
  for j in range(20):
   theta=-math.pi+j*TAU/20;phi=self.end(theta)
   start=Vector((math.sin(phi)*math.sin(theta),-math.sin(phi)*math.cos(theta),math.cos(phi)))
   pts=[];ws=[]
   for k in range(10):
    t=k/9;d=(start*(1-t)+target*t).normalized()
    angle=math.atan2(d.x,-d.y);ph=math.acos(max(-1,min(1,d.z)))
    pts.append(self.scalp(angle,ph,.0065+.001*math.sin(t*math.pi)))
    ws.append(.0007+.0045*math.sin(t*math.pi))
   self.tube(pts,ws,[.003]*10,6,.81+.07*math.sin(j*1.4))
 def braid(self):
  z=self.center.z
  guide=[self.scalp(math.pi,.25+2.0*k/20,.019) for k in range(21)]
  end=guide[-1]
  guide += [end+Vector((0,.045*k/12,-.20*k/12)) for k in range(1,13)]
  dist=[0]
  for a,b in zip(guide,guide[1:]):dist.append(dist[-1]+(b-a).length)
  def sample(t):
   d=t*dist[-1]
   for i in range(len(dist)-1):
    if dist[i+1]>=d:return guide[i].lerp(guide[i+1],(d-dist[i])/(dist[i+1]-dist[i]))
   return guide[-1]
  pts=[sample(k/35) for k in range(36)]
  self.tube(pts,[.019*(1-.69*k/35) for k in range(36)],sides=8,shade=.67,flatten=(0,1,0))
  n=24
  for i in range(n):
   t=i/n;center=sample(t);tangent=(sample(min(.999,t+.025))-sample(max(0,t-.025))).normalized()
   normal=Vector((0,-tangent.z,tangent.y)).normalized()
   if normal.y<0:normal=-normal
   width=.025*(1-.67*t)
   for sign in [-1,1]:
    points=[]
    for k in range(7):
     q=k/6;points.append(center+Vector((sign*width*(1-2*q),0,0))+tangent*((q-.5)*.022)+normal*(.008*math.sin(q*math.pi)))
    self.tube(points,[.002,.006,.008,.008,.007,.005,.0015],sides=6,shade=.9 if sign==1 else .8,flatten=normal)
  last=guide[-1]
  self.tube([last,last+Vector((0,.003,-.015)),last+Vector((.004,.006,-.038))],[.006,.009,.001],sides=8,shade=.86)
 def mohawk(self):
  # A continuous narrow fan broken into swept spikes from forehead to nape.
  for i in range(11):
   phi=-.86+i*2.71/10
   theta=0 if phi<0 else math.pi
   root=self.scalp(theta,abs(phi),.005);normal=(root-self.center).normalized()
   height=.029+.058*math.sin((i+1)/13*math.pi)
   tip=root+normal*height+Vector((0,.027,0))
   pts=[root,root+normal*height*.35,root+normal*height*.72+Vector((0,.013,0)),tip]
   self.tube(pts,[.017,.015,.009,.0007],[.021,.018,.013,.0007],8,.84+.06*math.sin(i),flatten=(0,1,0))
 def dreads(self):
  for j in range(25):
   theta=j*TAU/25
   front=math.cos(theta)>.5
   points=[];ws=[]
   for k in range(12):
    t=k/11
    if t<.56:
     phi=.20+(self.end(theta)-.20)*t/.56;p=self.scalp(theta+.3*(1-t),phi,.017)
    else:
     q=(t-.56)/.44;p=self.scalp(theta+.13,self.end(theta),.017)
     p.z-=(.013 if front else .16+.028*math.sin(j*2))*q
     p.x+=math.sin(theta)*(.026*q)+.005*math.sin(q*8+j)*q;p.y+=.025*q
    points.append(p);ws.append((.010+.002*math.sin(j*2))*(.6+.4*math.sin(math.pi*t*.82))*(.65 if k==11 else 1))
   self.tube(points,ws,sides=7,shade=.70+.16*(.5+.5*math.sin(j*2.7)),groove=.10)
 def make(self,sex,style,rig,mat):
  def deficit(p):
   d=p-self.center
   if p.z<self.center.z-.075 or d.length>.17:return 0
   r=d.length
   if r<.001:return 0
   d.normalize();hit,_,_,_=self.skull.ray_cast(self.center+d*.35,-d)
   if hit is None or (hit-self.center).length>.20:return 0
   return max(0,(hit-self.center).length+.0025-r)
  for _ in range(5):
   moves={i:deficit(p) for i,p in enumerate(self.v)}
   for f in self.f:
    if len(f)>4:continue
    d=deficit(sum((self.v[i] for i in f),Vector())/len(f))
    if d:
     for i in f:moves[i]=max(moves[i],d*1.1)
   if max(moves.values())<.0001:break
   for i,d in moves.items():
    if d:self.v[i]+=(self.v[i]-self.center).normalized()*d
  me=bpy.data.meshes.new(f'{sex}_{style}');me.from_pydata(self.v,[],self.f);me.update()
  o=bpy.data.objects.new(f'Hair_{sex}_{style}',me);bpy.context.collection.objects.link(o);me.materials.append(mat)
  for f in me.polygons:f.use_smooth=True
  # Recalculate winding for all closed locks; cap faces point outwards.
  bpy.context.view_layer.objects.active=o;o.select_set(True)
  bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.normals_make_consistent(inside=False);bpy.ops.object.mode_set(mode='OBJECT')
  attr=me.color_attributes.new(name='Color',type='BYTE_COLOR',domain='POINT');me.color_attributes.active_color=attr
  for i,c in enumerate(self.c):attr.data[i].color=(c,c,c,1)
  o.parent=rig;o.matrix_world=Matrix.Identity(4);o.modifiers.new('Head skin','ARMATURE').object=rig;o.vertex_groups.new(name='mixamorig:Head').add(list(range(len(self.v))),1,'REPLACE')
  dec=o.modifiers.new('Browser topology','DECIMATE');dec.ratio=.73 if style!='buzz_cut' else .9
  bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_move_up(modifier=dec.name);bpy.ops.object.modifier_apply(modifier=dec.name)
  return o

stats=[]
sexarg=args.sex
for sex,styles in STYLES.items():
 if sexarg and sex!=sexarg:continue
 s,body,rig,center,skull,mat=setup_scene(sex)
 for style in styles:
  bpy.ops.object.select_all(action='DESELECT');h=Hair(center,skull,style,sex)
  h.cap(style in ['buzz_cut','mohawk'])
  if style in ['ponytail','bun']:h.slick();getattr(h,'tail' if style=='ponytail' else 'bun')(*([sex] if style=='ponytail' else []))
  elif style=='short':h.flow(26,short=True)
  elif style=='long':h.curtain()
  elif style=='french_braid':h.slick();h.braid()
  elif style=='mullet':h.flow(22,short=True);h.curtain(True)
  elif style=='mohawk':h.mohawk()
  elif style=='shaggy':h.flow(32,shag=True,short=True)
  elif style=='dreads':h.dreads()
  o=h.make(sex,style,rig,mat)
  bpy.ops.object.select_all(action='DESELECT');o.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
  path=OUT/'Models'/f'{sex}_{style}.glb'
  bpy.ops.export_scene.gltf(filepath=str(path),use_selection=True,export_format='GLB',export_animations=False,export_extras=False,export_cameras=False,export_lights=False,export_yup=True)
  me=o.data;me.calc_loop_triangles();stats.append({'sex':sex,'style':style,'vertices':len(me.vertices),'triangles':len(me.loop_triangles),'bytes':path.stat().st_size})
  # Warm chestnut preview; the exported material remains neutral and tintable.
  vc=mat.node_tree.nodes.get('HairColor');bs=mat.node_tree.nodes.get('Principled BSDF');mix=mat.node_tree.nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1;mix.inputs[2].default_value=(.16,.070,.032,1);mat.node_tree.links.new(vc.outputs['Color'],mix.inputs[1]);mat.node_tree.links.new(mix.outputs[0],bs.inputs['Base Color'])
  target=Vector((0,.018,1.62))
  for label,offset in [('front',(0.7,-1.5,.36)),('back',(.85,1.5,.40)),('side',(1.5,-.20,.20))]:
   s.camera.location=target+Vector(offset);aim(s.camera,target);s.render.filepath=str(OUT/'Previews'/f'{sex}_{style}_{label}.png');bpy.ops.render.render(write_still=True)
  mat.node_tree.nodes.remove(mix);mat.node_tree.links.new(vc.outputs['Color'],bs.inputs['Base Color'])
  o.hide_render=True;o.hide_set(True)
 first=bpy.data.objects.get(f'Hair_{sex}_{styles[0]}');first.hide_render=False;first.hide_set(False)
 bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Sources'/f'{sex}_Hair.blend'),compress=True)
(OUT/f'stats{sexarg or ""}.json').write_text(json.dumps(stats,indent=2))
