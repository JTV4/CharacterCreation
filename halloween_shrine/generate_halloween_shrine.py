"""GrindScape Harvest Warden — deterministic, texture-free browser asset.
Run with Blender 4.1+: blender --background --python this_file.py
Source is Z-up, faces -Y; GLB is Y-up, faces +Z. No runtime lights.
"""
import bpy, bmesh, math, random, json, os
from mathutils import Vector
from math import sin, cos, pi
from pathlib import Path

ROOT = Path(__file__).resolve().parent
random.seed(31026)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
asset = bpy.data.collections.new('HARVEST_WARDEN_SOURCE')
scene.collection.children.link(asset)
MATS = {}
def material(name, metallic=0, emission=False):
    m=bpy.data.materials.new(name); m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF'); bs.inputs['Roughness'].default_value=.78 if not metallic else .38
    bs.inputs['Metallic'].default_value=metallic
    bs.inputs['Specular IOR Level'].default_value=.24
    vc=m.node_tree.nodes.new('ShaderNodeVertexColor'); vc.layer_name='Color'
    m.node_tree.links.new(vc.outputs['Color'],bs.inputs['Base Color'])
    if emission:
        # glTF has no vertex-color emission input: use a portable constant.
        bs.inputs['Emission Color'].default_value=(1,.22,.005,1)
        bs.inputs['Emission Strength'].default_value=2.5
    MATS[name]=m
    return m
MAT=material('Warden_Matte'); GOLD=material('Warden_AntiqueGold',.65); GLOW=material('Warden_Ember',emission=True)
stone=(.12,.13,.165); wood=(.095,.034,.012); purple=(.065,.014,.12); straw=(.48,.22,.035); gold=(.72,.30,.025); orange=(.62,.105,.005)

def paint(o,col,mat=MAT,var=.09):
    o.data.materials.clear(); o.data.materials.append(mat)
    c=o.data.color_attributes.new(name='Color',type='BYTE_COLOR',domain='CORNER')
    for p in o.data.polygons:
        f=random.uniform(1-var,1+var)
        for li in p.loop_indices: c.data[li].color=(*[min(1,max(.001,v*f)) for v in col],1)
    for coll in list(o.users_collection): coll.objects.unlink(o)
    asset.objects.link(o)
    return o
def mesh(name,verts,faces,col,mat=MAT,var=.08):
    me=bpy.data.meshes.new(name); me.from_pydata(verts,[],faces); me.update()
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(name,me); asset.objects.link(o)
    return paint(o,col,mat,var)
def box(name,loc,size,col,bevel=.035,mat=MAT,rot=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=name; o.dimensions=size; o.rotation_euler.z=rot
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bevel:
        mod=o.modifiers.new('Chipped edges','BEVEL'); mod.width=bevel; mod.segments=1
        bpy.ops.object.modifier_apply(modifier=mod.name)
    return paint(o,col,mat)
def beam(name,a,b,r1,r2,col=wood,n=7,mat=MAT):
    a,b=Vector(a),Vector(b); d=b-a
    bpy.ops.mesh.primitive_cone_add(vertices=n,radius1=r1,radius2=r2,depth=d.length,location=(a+b)/2)
    o=bpy.context.object; o.name=name; o.rotation_euler=d.to_track_quat('Z','Y').to_euler()
    return paint(o,col,mat)
def tube(name,pts,radii,col,n=7,mat=MAT):
    vs=[]; fs=[]
    for i,p in enumerate(pts):
        tangent=Vector(pts[min(i+1,len(pts)-1)])-Vector(pts[max(0,i-1)])
        q=tangent.to_track_quat('Z','Y')
        for j in range(n):
            v=Vector(p)+q@Vector((radii[i]*cos(j*2*pi/n),radii[i]*sin(j*2*pi/n),0)); vs.append(v)
    for i in range(len(pts)-1):
        for j in range(n): a=i*n+j;b=i*n+(j+1)%n;fs.append((a,b,b+n,a+n))
    fs.extend([tuple(range(n-1,-1,-1)),tuple((len(pts)-1)*n+j for j in range(n))])
    return mesh(name,vs,fs,col,mat)
def ring(name,center,radius,minor,col,axis='Z',mat=MAT,n=20,k=5):
    vs=[];fs=[]
    for i in range(n):
        a=2*pi*i/n
        for j in range(k):
            b=2*pi*j/k; v=((radius+minor*cos(b))*cos(a),(radius+minor*cos(b))*sin(a),minor*sin(b))
            if axis=='Y': v=(v[0],v[2],v[1])
            if axis=='X': v=(v[2],v[0],v[1])
            vs.append(tuple(center[t]+v[t] for t in range(3)))
    for i in range(n):
        for j in range(k):fs.append((i*k+j,((i+1)%n)*k+j,((i+1)%n)*k+(j+1)%k,i*k+(j+1)%k))
    return mesh(name,vs,fs,col,mat)
def leaf(name,a,b,width,col=straw):
    a,b=Vector(a),Vector(b); d=b-a
    side=d.cross(Vector((0,-1,.2))).normalized()*width
    mid=a+d*.48; ridge=mid+Vector((0,-width*.32,0))
    return mesh(name,[a-side*.4,a+side*.4,mid+side,b,mid-side,ridge],[(0,1,5),(1,2,5),(2,3,5),(3,4,5),(4,0,5)],col)
def poly_front(name,coords,y,col,mat=MAT):
    # x,z coordinates counterclockwise as seen from the front.
    return mesh(name,[(x,y,z) for x,z in coords],[tuple(range(len(coords)))],col,mat,0)
def bat(cx,y,cz,s):
    p=[(-1,.3),(-.63,.16),(-.34,.38),(-.15,.08),(-.12,.24),(0,.14),(.12,.24),(.15,.08),(.34,.38),(.63,.16),(1,.3),(.77,-.12),(.5,-.08),(.28,-.26),(0,-.58),(-.28,-.26),(-.5,-.08),(-.77,-.12)]
    poly_front('Gilded bat sigil',[(cx+x*s,cz+z*s) for x,z in reversed(p)],y,gold,GOLD)

# Broad stepped stone dais; each block reads clearly from the game camera.
box('Dais dark mortar',(0,0,.16),(4.5,2.95,.3),(.09,.095,.12),.12)
for layer in range(2):
    z=.16+layer*.28
    for side in [-1,1]:
        for j in range(3):
            box('Foundation ashlar',(side*(1.40+j*.36),-1.24,z),(.345,.49,.27),stone,.035)
        for j in range(5):
            box('Side foundation',(side*2.12,-.78+j*.49,z),(.43,.47,.27),stone,.045)
    for j in range(8):box('Rear foundation',(-1.645+j*.47,1.23,z),(.455,.44,.27),stone,.04)
box('Lowest offering step',(0,-1.58,.12),(2.7,.8,.24),stone,.07)
box('Upper offering step',(0,-1.25,.33),(2.27,.65,.24),(.25,.26,.3),.055)
box('Dais paving',(0,0,.48),(3.88,2.6,.14),(.235,.225,.25),.05)
for s in [-1,1]:
    for row in range(3):
        for j in range(3):
            box('Wing wall stone',(s*(1.29+j*.36),-.72,.69+row*.27),(.34,.47,.255),stone,.03)
    box('Wing wall coping',(s*1.65,-.72,1.43),(1.2,.62,.16),(.28,.28,.325),.035)
    box('Raised shrine gatepost',(s*1.12,-.81,1.08),(.29,.61,1.14),(.28,.26,.3),.04)
    beam('Gate finial',(s*1.12,-.81,1.66),(s*1.12,-.81,1.99),.19,0,stone,4)
    # Low relief spear-shaped gold accents.
    x=s*1.12
    poly_front('Gate golden diamond',[(x,1.73),(x-.16,1.36),(x,1.05),(x+.16,1.36)],-1.122,gold,GOLD)
    beam('Diamond ridge',(x,-1.14,1.12),(x,-1.14,1.67),.018,.015,gold,4,GOLD)

# A bound, tapered bundle of timber forms the body (no humanoid anatomy).
for i in range(11):
    a=2*pi*i/11
    beam('Warden body timber',(.98*cos(a),.25+.56*sin(a),.6),(.56*cos(a),.24+.37*sin(a),3.65+random.uniform(-.18,.18)),.16,.105,tuple(v*random.uniform(.8,1.25) for v in wood))
for z,r in [(1.55,.83),(2.38,.68),(3.24,.56)]:
    # Broad encircling bands plus front cross braces.
    for i in range(10):
        a=2*pi*i/10;b=2*pi*(i+1)/10
        beam('Iron binding',(r*cos(a),.24+r*.64*sin(a),z), (r*cos(b),.24+r*.64*sin(b),z),.065,.065,(.105,.10,.13),4)
for s in [-1,1]:
    beam('Diagonal timber brace',(s*.94,-.38,1.15),(-s*.57,-.23,3.25),.095,.075,(.27,.115,.042),5)
    for z in [1.68,2.63]:
        t=(z-1.15)/2.1;x=s*(.94-1.51*t);y=-.38+.15*t-.09
        beam('Iron peg',(x,y,z),(x,y-.025,z),.04,.04,gold,6,GOLD)

# Unequal gnarled branch arms, forked tips and visible bark facets.
arm_paths=[]
for s in [-1,1]:
    pts=[(s*.3,.19,3.61),(s*.94,.18,3.78),(s*1.67,.15,3.72),(s*2.4,.16,4.0),(s*3.16,.19,4.3 if s<0 else 4.15)]
    arm_paths.append(pts);tube('Crooked harvest bough',pts,[.22,.23,.20,.16,.085],wood,8)
    tube('Bark highlight',[(x,y-.12,z+.055) for x,y,z in pts],[.04,.055,.035,.035,.015],(.32,.135,.041),5)
    for idx in [2,3]:
        x,y,z=pts[idx]
        tube('Broken branch fork',[(x,y,z),(x-s*.04,y+.015,z+.24),(x+s*.1,y+.06,z+.47)],[.08,.065,.006],wood,5)
    for x,z in [(s*1.05,3.79),(s*2.48,4.03)]:
        for k in range(4):ring('Hemp arm binding',(x+(k-1.5)*.055,.16,z),.19,.032,(.55,.3,.10),'X',n=10,k=4)

# Folded, pointed straw tufts, not alpha cards.
for s in [-1,1]:
    for i in range(35):
        a=(s*random.uniform(.34,.82),random.uniform(-.24,.49),random.uniform(3.40,3.76))
        b=(s*random.uniform(.85,1.52),a[1]+random.uniform(-.3,.2),random.uniform(2.87,3.66))
        leaf('Shoulder straw',a,b,random.uniform(.055,.14),tuple(v*random.uniform(.8,1.3) for v in straw))
    for i in range(15):
        a=(s*random.uniform(.79,1.1),random.uniform(-.35,.48),random.uniform(.98,1.3))
        b=(a[0]+s*random.uniform(.05,.38),a[1]-.13,random.uniform(.52,.85))
        leaf('Dais straw bundle',a,b,.075,straw)
    for i in range(7):
        beam('Timber splinter',(s*.8,.28,1.25),(s*random.uniform(1.1,1.44),.31,random.uniform(1.55,1.87)),.045,0,wood,4)

def banner(name,cx,y,z,width,length,emblem=True):
    vs=[];rows=7;cols=5
    for j in range(rows):
        t=j/(rows-1)
        for i in range(cols):
            u=i/(cols-1); zz=z-t*length
            if j==rows-1:zz+=abs(u-.5)*.47 + (.10 if i%2 else 0)
            vs.append((cx+(u-.5)*width*(1-.15*t),y+sin(u*pi*3+t*3)*.055,zz))
    fs=[]
    for j in range(rows-1):
        for i in range(cols-1):a=j*cols+i;fs.append((a,a+cols,a+cols+1,a+1))
    o=mesh(name,vs,fs,purple)
    # Back faces are explicit so no double-sided rendering is needed.
    solid=o.modifiers.new('Heavy cloth thickness','SOLIDIFY');solid.thickness=.012
    bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=solid.name)
    # Two worn edge strips.
    for s in [-1,1]:
        for j in range(5):
            t=j/6; x=cx+s*width*.46*(1-.15*t)
            leaf('Banner worn gold edging',(x,y-.072,z-t*length),(x-s*.022,y-.072,z-(t+.12)*length),.022,gold)
    if emblem:bat(cx,y-.091,z-length*.53,width*.35)
banner('Great offering pennant',0,-.52,3.53,.77,2.02)
banner('Left bough pennant',-2.15,.10,3.87,.56,1.22)
banner('Right bough pennant',2.12,.10,3.85,.56,1.4)
bat(0,-.615,1.93,.20)

def pumpkin(name,c,r,main=False):
    # Lobed lathe with recessed poles; sharp material facets follow each rib.
    n=48 if main else 24;m=14 if main else 9
    vs=[]; fs=[]
    for j in range(m+1):
        t=pi*(.025+.95*j/m)
        for i in range(n):
            a=2*pi*i/n; rr=r*sin(t)*(1+.095*cos(8*a))
            vs.append((c[0]+rr*cos(a),c[1]+rr*sin(a)*.83,c[2]+r*cos(t)*.91))
    for j in range(m):
        for i in range(n):a=j*n+i;b=j*n+(i+1)%n;fs.append((a,b,b+n,a+n))
    fs += [tuple(range(n-1,-1,-1)),tuple(m*n+i for i in range(n))]
    shell=mesh(name,vs,fs,orange,var=.16)
    # Cut actual silhouette holes, then place luminous faces just inside.
    eyes=[[(-.64,.35),(-.14,.14),(-.45,-.025)],[(.64,.35),(.45,-.025),(.14,.14)]]
    mouth=[(-.65,-.24),(-.40,-.33),(-.23,-.22),(-.06,-.39),(.14,-.26),(.3,-.32),(.58,-.18),(.46,-.49),(.25,-.59),(.04,-.53),(-.14,-.63),(-.35,-.52),(-.53,-.49)]
    nose=[(-.08,-.11),(.09,-.14),(.03,.05)]
    for pts in eyes+[mouth,nose]:
        vv=[(c[0]+x*r,c[1]+yy*r,c[2]+z*r) for yy in [-1.5,.08] for x,z in pts]
        l=len(pts);ff=[tuple(range(l-1,-1,-1)),tuple(range(l,2*l))]+[(i,(i+1)%l,(i+1)%l+l,i+l) for i in range(l)]
        cut=mesh('temporary carving tool',vv,ff,(0,0,0))
        mod=shell.modifiers.new('Carved jack o lantern','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cut
        bpy.context.view_layer.objects.active=shell
        bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cut,do_unlink=True)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=r*.82,location=c)
    inner=bpy.context.object;inner.name='Enclosed lantern ember core';inner.scale=(1,.83,.91)
    paint(inner,(1,.30,.008),GLOW,0)
    tube('Twisted pumpkin stem',[(c[0],c[1],c[2]+r*.84),(c[0]-.06*r,c[1],c[2]+r*1.13),(c[0]+.12*r,c[1],c[2]+r*1.27)],[r*.12,r*.095,r*.035],(.19,.12,.028),6)
    return shell

head=pumpkin('Great carved pumpkin',(0,-.05,4.2),.66,True)
for i in range(27):
    a=2*pi*i/27
    leaf('Raffia collar',(.34*cos(a),.02+.25*sin(a),3.79),(.60*cos(a),.02+.43*sin(a),3.37-random.random()*.18),.075,straw)

# Slouching witch hat: asymmetric elliptical brim and bent segmented crown.
vs=[];fs=[];n=40
for ring_i in range(3):
    for i in range(n):
        a=i*2*pi/n
        if ring_i==0:rx,ry=.53,.46
        elif ring_i==1:rx,ry=.97,.65
        else:rx,ry=1.39*(1+random.uniform(-.06,.06)),.85
        z=4.68+.09*cos(a)+(.16*sin(2*a) if ring_i else 0)-.07*ring_i
        vs.append((rx*cos(a),.04+ry*sin(a),z))
for j in range(2):
    for i in range(n):fs.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
hat=mesh('Ragged witch brim',vs,fs,(.105,.032,.17),var=.16)
mod=hat.modifiers.new('Brim thickness','SOLIDIFY');mod.thickness=.04;bpy.context.view_layer.objects.active=hat;bpy.ops.object.modifier_apply(modifier=mod.name)
tube('Bent witch crown',[(0,.05,4.68),(-.05,.08,4.94),(-.11,.11,5.28),(.02,.13,5.56),(.29,.13,5.65),(.52,.12,5.4),(.7,.13,5.5)],[.51,.43,.31,.23,.16,.085,0],purple,12)
tube('Hat ochre band',[(0,.05,4.72),(-.04,.078,4.91)],[.524,.454],(.50,.24,.065),12)
# Square buckle from four beveled bars.
for x in [-.145,.145]:box('Witch hat buckle',(x-.035,-.43,4.82),(.055,.04,.22),gold,.012,GOLD)
for z in [4.71,4.93]:box('Witch hat buckle',(-.035,-.43,z),(.34,.04,.05),gold,.01,GOLD)
for s in [-1,1]:
    for i in range(12):
        a=(s*random.uniform(.44,.66),random.uniform(-.15,.3),4.51)
        leaf('Wild straw hair',a,(s*random.uniform(.65,.91),a[1]-.06,random.uniform(3.69,4.18)),.055,straw)

# Five suspended lanterns create the same wide visual rhythm as the reference.
for i,(x,y,z,r,hang) in enumerate([(-2.95,.14,3.50,.235,.73),(-1.55,.11,2.91,.255,.82),(1.46,.11,2.79,.23,.94),(2.96,.17,3.34,.235,.79),(.73,.12,4.88,.17,.43)]):
    pumpkin('Hanging lantern %d'%i,(x,y,z),r)
    tube('Twisted suspension cord',[(x,y,z+r*1.18),(x-.035,y,z+r+hang*.5),(x+.025,y,z+r+hang)],[.018,.019,.018],(.49,.26,.073),5)
    ring('Lantern loop',(x,y,z+r*1.27),.058,.015,straw,'Y',n=8,k=4)

# Chest sunburst seal and an accessible coin basin.
def medallion(cx,y,z,r):
    beam('Gilded pumpkin seal',(cx,y+.05,z),(cx,y-.025,z),r,r,gold,16,GOLD)
    ring('Raised seal rim',(cx,y-.045,z),r*.86,r*.055,(.97,.51,.09),'Y',GOLD,n=20,k=4)
    for s in [-1,1]:
        poly_front('Seal engraved eye',[(cx+s*r*.12,z+r*.08),(cx+s*r*.49,z+r*.26),(cx+s*r*.32,z-r*.08)],y-.085,(.15,.06,.009))
    poly_front('Seal wicked grin',[(cx-r*.5,z-r*.22),(cx-r*.18,z-r*.31),(cx,z-r*.18),(cx+r*.17,z-r*.33),(cx+r*.5,z-r*.19),(cx+r*.27,z-r*.52),(cx-r*.24,z-r*.52)],y-.085,(.15,.06,.009))
medallion(0,-.66,3.36,.31)
box('Offering altar',(0,-.82,.85),(1.32,.83,.65),stone,.055)
box('Altar cornice',(0,-.83,1.19),(1.48,.92,.15),(.30,.29,.32),.035)
medallion(0,-1.282,.86,.31)
# Bowl profile: closed bottom, open mouth, thick stone lip.
vs=[];fs=[];profiles=[(.44,1.22),(.62,1.35),(.66,1.5),(.59,1.52),(.51,1.36),(.0,1.31)]
for r,z in profiles:
    for i in range(20):a=2*pi*i/20;vs.append((r*cos(a),-.78+r*.73*sin(a),z))
for j in range(len(profiles)-1):
    for i in range(20):a=j*20+i;b=j*20+(i+1)%20;fs.append((a,b,b+20,a+20))
mesh('Offering basin',vs,fs,(.22,.215,.25))
ring('Basin brass rim',(0,-.78,1.50),.625,.023,gold,mat=GOLD,n=20,k=4).scale.y=.73
# Low-poly embossed coins, fixed to the bowl and lower stair.
for i in range(52):
    if i<35:
        a=random.random()*2*pi; rr=.48*math.sqrt(random.random());x=rr*cos(a);y=-.78+rr*sin(a)*.7;z=1.355+.12*(1-rr/.5)+random.uniform(0,.055)
    else:x=random.uniform(-.67,.67);y=random.uniform(-1.55,-1.15);z=.475
    o=beam('Offerings coin',(x,y,z),(x,y,z+.028),.062,.062,(.8,.34,.025),10,GOLD)
    o.rotation_euler.x+=random.uniform(-.3,.3);o.rotation_euler.y+=random.uniform(-.3,.3)
    if i%3==0:ring('Coin stamped rim',(x,y,z+.03),.043,.006,(1,.64,.14),mat=GOLD,n=8,k=3)

# Source remains editable. Runtime meshes are consolidated into three material batches.
bpy.ops.object.select_all(action='DESELECT')
for o in asset.objects:
    o.select_set(True)
bpy.context.view_layer.objects.active=head
bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
for o in asset.objects:
    o['asset']='Harvest Warden';o['role']='static seasonal structure'
scene['asset_front']='Blender -Y / glTF +Z';scene['asset_units']='meters'
source_objects=list(asset.objects)
runtime=bpy.data.collections.new('RUNTIME_EXPORT');scene.collection.children.link(runtime)
runtime_objects=[]
for mat in [MAT,GOLD,GLOW]:
    copies=[]
    for o in source_objects:
        if o.type=='MESH' and o.data.materials[0]==mat:
            d=o.copy();d.data=o.data.copy();runtime.objects.link(d);copies.append(d)
    bpy.ops.object.select_all(action='DESELECT')
    for o in copies:o.select_set(True)
    bpy.context.view_layer.objects.active=copies[0];bpy.ops.object.join()
    o=bpy.context.object;o.name={'Warden_Matte':'Shrine_Structure','Warden_AntiqueGold':'Shrine_Gold','Warden_Ember':'Shrine_Embers'}[mat.name]
    tri=o.modifiers.new('Game triangulation','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tri.name)
    runtime_objects.append(o)
for name,pos in [('OfferingPoint',(0,-.78,1.5)),('InteractionPoint',(0,-2.2,0)),('NameplatePoint',(0,0,5.95))]:
    o=bpy.data.objects.new(name,None);runtime.objects.link(o);o.location=pos;o.empty_display_size=.15;runtime_objects.append(o)
def export(path,objs):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:o.hide_set(False);o.select_set(True)
    bpy.context.view_layer.objects.active=objs[0]
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_apply=True,export_extras=True,export_animations=False,export_cameras=False,export_lights=False,export_yup=True)
export(ROOT/'HalloweenOfferingShrine.glb',runtime_objects)
stats={'name':'Harvest Warden','lod0_triangles':sum(len(o.data.polygons) for o in runtime_objects if o.type=='MESH'),'materials':3,'draw_calls':3,'textures':0,'runtime_lights':0}
# Conservatively simplify only matte geometry. Gold/face features remain readable.
lod=[]
runtime_names=[o.name for o in runtime_objects]
for o in runtime_objects:o.name=o.name+'_LOD0Hidden'
for o,base_name in zip(runtime_objects,runtime_names):
    d=o.copy()
    if o.type=='MESH':
        d.data=o.data.copy()
    runtime.objects.link(d);d.name=base_name;lod.append(d)
    if o.type=='MESH':
        mod=d.modifiers.new('Distance LOD','DECIMATE');mod.ratio=.43 if 'Structure' in o.name else .65
        bpy.context.view_layer.objects.active=d;bpy.ops.object.modifier_apply(modifier=mod.name)
        tri=d.modifiers.new('Triangles','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=tri.name)
export(ROOT/'HalloweenOfferingShrine_LOD1.glb',lod)
stats['lod1_triangles']=sum(len(o.data.polygons) for o in lod if o.type=='MESH')
for o in lod:bpy.data.objects.remove(o,do_unlink=True)
for o,name in zip(runtime_objects,runtime_names):o.name=name
for o in runtime_objects:o.hide_render=True;o.hide_set(True)
stats['dimensions_m']=[round(max(v.co[a] for o in source_objects for v in o.data.vertices)-min(v.co[a] for o in source_objects for v in o.data.vertices),3) for a in range(3)]
(ROOT/'asset_stats.json').write_text(json.dumps(stats,indent=2))

# Presentation rig is excluded from GLB exports.
rig=bpy.data.collections.new('PREVIEW_ONLY');scene.collection.children.link(rig)
def rig_obj(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    rig.objects.link(o)
def point(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.055));floor=bpy.context.object;floor.name='Preview ground';rig_obj(floor)
fm=bpy.data.materials.new('Preview ground');fm.diffuse_color=(.075,.085,.105,1);floor.data.materials.append(fm)
for name,loc,power,color,size in [('Warm key',(-4,-6,9),1450,(1,.80,.60),5),('Cool fill',(5,-1,6),1100,(.53,.66,1),4),('Rim',(1,4,8),1900,(1,.51,.19),4)]:
    bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.name=name;rig_obj(o);o.data.energy=power;o.data.color=color;o.data.shape='DISK';o.data.size=size;point(o,(0,0,2.5))
bpy.ops.object.camera_add(location=(7,-13,8));cam=bpy.context.object;rig_obj(cam);cam.data.type='ORTHO';cam.data.ortho_scale=8.1;point(cam,(0,0,2.75));scene.camera=cam
scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
scene.world=bpy.data.worlds.new('Studio world');scene.world.color=(.22,.22,.22)
scene.render.resolution_x=1400;scene.render.resolution_y=1400;scene.render.resolution_percentage=100
scene.view_settings.view_transform='AgX'
scene.use_nodes=True;nt=scene.node_tree;nt.nodes.clear();rl=nt.nodes.new('CompositorNodeRLayers');gl=nt.nodes.new('CompositorNodeGlare');gl.glare_type='FOG_GLOW';gl.threshold=1.7;gl.quality='HIGH';gl.mix=-.92;out=nt.nodes.new('CompositorNodeComposite');nt.links.new(rl.outputs['Image'],gl.inputs[0]);nt.links.new(gl.outputs[0],out.inputs[0])
# Default Blender viewport frames the art and hides preview helpers.
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_distance=10
            area.spaces.active.region_3d.view_location=(0,0,2.7)
            area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
            area.spaces.active.shading.type='MATERIAL'
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'HalloweenOfferingShrine.blend'))
for name,loc,scale in [('hero',(6.7,-14,7.4),7.85),('front',(0,-15,6.2),7.55),('game_view',(8,-11,11),8.1),('rear',(7,12,7),7.85)]:
    cam.location=loc;cam.data.ortho_scale=scale;point(cam,(0,0,2.73));scene.render.filepath=str(ROOT/(name+'.png'));bpy.ops.render.render(write_still=True)
print('ASSET_STATS '+json.dumps(stats))
