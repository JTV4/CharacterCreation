"""Keep only head skinning and its ancestor chain, then repack used GLB accessors."""
import json,struct,sys
from pathlib import Path
P=Path(sys.argv[1]) if len(sys.argv)>1 else Path('rework_hair')
manifest=[]
for p in sorted((P/'Models').glob('*.glb')):
 raw=p.read_bytes();jl=struct.unpack_from('<I',raw,12)[0];g=json.loads(raw[20:20+jl]);binary=raw[28+jl:]
 def accessor_bytes(idx):
  a=g['accessors'][idx];v=g['bufferViews'][a['bufferView']];start=v.get('byteOffset',0)+a.get('byteOffset',0);size={5121:1,5123:2,5125:4,5126:4}[a['componentType']]*{'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']];stride=v.get('byteStride',size)
  return b''.join(binary[start+i*stride:start+i*stride+size] for i in range(a['count']))
 skin=g['skins'][0];head=next(i for i,n in enumerate(g['nodes']) if n.get('name','').replace(':','')=='mixamorigHead');headidx=skin['joints'].index(head)
 overrides={}
 for mesh in g['meshes']:
  for prim in mesh['primitives']:
   ja=prim['attributes']['JOINTS_0'];wa=prim['attributes']['WEIGHTS_0'];weights=accessor_bytes(wa);joints=accessor_bytes(ja);a=g['accessors'][ja]
   jfmt={5121:'B',5123:'H'}[a['componentType']]
   for i in range(a['count']):
    w=struct.unpack_from('<4f',weights,i*16);j=struct.unpack_from('<4'+jfmt,joints,i*4*struct.calcsize(jfmt))
    assert all(wi==0 or ji==headidx for wi,ji in zip(w,j)),(p,i,w,j)
   a['componentType']=5121;a.pop('min',None);a.pop('max',None);overrides[ja]=bytes(a['count']*4)
 ib=skin['inverseBindMatrices'];overrides[ib]=accessor_bytes(ib)[headidx*64:(headidx+1)*64];g['accessors'][ib]['count']=1
 skin['joints']=[head]
 parents={child:i for i,n in enumerate(g['nodes']) for child in n.get('children',[])}
 keep={head}|{i for i,n in enumerate(g['nodes']) if 'mesh' in n}
 for idx in list(keep):
  while idx in parents:idx=parents[idx];keep.add(idx)
 order=sorted(keep);remap={old:new for new,old in enumerate(order)}
 nodes=[]
 for idx in order:
  n=g['nodes'][idx]
  if 'children' in n:
   n['children']=[remap[c] for c in n['children'] if c in keep]
   if not n['children']:n.pop('children')
  nodes.append(n)
 g['nodes']=nodes;skin['joints']=[remap[head]]
 if 'skeleton' in skin:skin['skeleton']=remap[skin['skeleton']]
 for scene in g['scenes']:scene['nodes']=[remap[n] for n in scene['nodes'] if n in keep]
 # glTF skin matrices already produce world-space vertices; use root mesh nodes.
 mesh_nodes={i for i,n in enumerate(nodes) if 'mesh' in n}
 for n in nodes:
  if 'children' in n:n['children']=[i for i in n['children'] if i not in mesh_nodes]
 for scene in g['scenes']:scene['nodes']+=sorted(mesh_nodes-set(scene['nodes']))
 for m in g['materials']:m['doubleSided']=False
 chunks=bytearray();views=[]
 for i,a in enumerate(g['accessors']):
  data=overrides[i] if i in overrides else accessor_bytes(i)
  while len(chunks)%4:chunks.append(0)
  v={'buffer':0,'byteOffset':len(chunks),'byteLength':len(data)}
  oldv=g['bufferViews'][a['bufferView']]
  if 'target' in oldv:v['target']=oldv['target']
  a['bufferView']=len(views);a.pop('byteOffset',None);views.append(v);chunks.extend(data)
 g['bufferViews']=views;g['buffers']=[{'byteLength':len(chunks)}]
 while len(chunks)%4:chunks.append(0)
 j=json.dumps(g,separators=(',',':')).encode();j+=b' '*((-len(j))%4)
 out=struct.pack('<4sII',b'glTF',2,28+len(j)+len(chunks))+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(chunks),0x004e4942)+chunks;p.write_bytes(out)
 prim=g['meshes'][0]['primitives'][0];manifest.append({'file':p.name,'triangles':g['accessors'][prim['indices']]['count']//3,'vertices':g['accessors'][prim['attributes']['POSITION']]['count'],'bytes':len(out),'meshes':len(g['meshes']),'materials':len(g['materials']),'skinJoints':len(skin['joints']),'textures':len(g.get('textures',[]))})
(P/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
