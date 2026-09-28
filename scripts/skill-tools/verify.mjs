import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from '../../viewer/node_modules/typescript/lib/typescript.js';
import { T, P, rig } from './rig.mjs';
async function source(relative) {
 const path=new URL('../../viewer/src/'+relative,import.meta.url);
 const js=ts.transpileModule(fs.readFileSync(path,'utf8'),{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText.replaceAll('"three"',JSON.stringify(new URL('../../viewer/node_modules/three/build/three.module.js',import.meta.url).href)).replaceAll("'three'",JSON.stringify(new URL('../../viewer/node_modules/three/build/three.module.js',import.meta.url).href));
 return import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
}
const {createFishingLine,createSpellEffect,SPELL_STYLES}=await source('utils/toolEffects.ts');
const {fishingMount,createFishingCarryMount}=await source('utils/fishingMount.ts');
const {createFishingGrip}=await source('utils/fishingGrip.ts');
const rodData=JSON.parse(fs.readFileSync(new URL('./rod-rig.json',import.meta.url)));
const {animSpecToClip}=await source('utils/animSpecToClip.ts');
const report={animations:[],rods:[],spells:[]};
for(const sex of ['Female','Male'])for(const kind of ['Fishing','MagicCast']) {
 const spec=JSON.parse(fs.readFileSync(`${P}/animations/${sex}${kind}.anim.json`));
 const {root,by,bones,rest}=rig(sex);
 const resting=new Map([...rest].map(([n,v])=>[n,{position:v.p,quaternion:v.q}]));
 const scale=by.get('Hips').parent.getWorldScale(new T.Vector3()).y;
 const feet=['LeftFoot','RightFoot'].map(n=>({b:by.get(n),p:by.get(n).getWorldPosition(new T.Vector3())}));
 for(const track of spec.tracks) {
  assert.equal(track.keyframes[0].time,0);
  assert.equal(track.keyframes.at(-1).time,spec.meta.duration);
  for(const key of track.keyframes){assert(key.value.every(Number.isFinite));if(track.property==='rotation')assert(Math.abs(Math.hypot(...key.value)-1)<1e-6);}
  for(let i=0;i<track.keyframes[0].value.length;i++)assert(Math.abs(track.keyframes[0].value[i]-track.keyframes.at(-1).value[i])<1e-5,'loop discontinuity');
 }
 const mixer=new T.AnimationMixer(root),action=mixer.clipAction(animSpecToClip(spec,resting,.01/scale));action.play();action.paused=true;
 let worst=0, maximumWristBend=0;
 for(let i=0;i<spec.meta.duration*30;i++) {
  action.time=i/30;mixer.update(0);root.updateMatrixWorld(true);
  if(i===0 && kind==='Fishing')for(const f of feet)f.p.copy(f.b.getWorldPosition(new T.Vector3()));
  for(const f of feet)worst=Math.max(worst,f.p.distanceTo(f.b.getWorldPosition(new T.Vector3())));
  for(const b of bones)assert(b.matrixWorld.elements.every(Number.isFinite));
  if(kind==='Fishing') {
   const hand=by.get('RightHand'),handQ=hand.getWorldQuaternion(new T.Quaternion());
   const shaft=new T.Vector3(Math.cos(.55),Math.sin(.55),0).applyQuaternion(handQ);
   assert(Math.abs(shaft.x)<1e-5 && shaft.z>.62,'rod must point forward, not sideways');
   const handMatrix=new T.Matrix4().compose(hand.getWorldPosition(new T.Vector3()),handQ,new T.Vector3(1,1,1));
   const palm=new T.Vector3(0,.105,.024).applyQuaternion(handQ).add(hand.getWorldPosition(new T.Vector3()));
   const left=by.get('LeftHand'),support=new T.Vector3(0,.105,.024).applyQuaternion(left.getWorldQuaternion(new T.Quaternion())).add(left.getWorldPosition(new T.Vector3()));
   assert(palm.z>.25,'grip is too close to the torso');
   assert(support.distanceTo(palm.clone().addScaledVector(shaft,.10))<.001,'supporting hand left the handle');
   for(const anchor of Object.values(rodData)){
    const model=new T.Group();
    for(const [name,point] of [['FishingGrip',anchor.grip],['FishingTip',anchor.tip]]){const n=new T.Object3D();n.name=name;n.position.fromArray(point);model.add(n);}
    const mount=fishingMount(model),matrix=handMatrix.clone().multiply(new T.Matrix4().compose(mount.position,mount.quaternion,new T.Vector3(1,1,1)));
    const grip=new T.Vector3(...anchor.grip).applyMatrix4(matrix);
    assert(grip.distanceTo(new T.Vector3(0,.105,.024).applyMatrix4(handMatrix))<1e-7,'handle escaped palm');
    const tip=new T.Vector3(...anchor.tip).applyMatrix4(matrix).applyAxisAngle(new T.Vector3(1,0,0),Math.PI/2);
    const line=createFishingLine();line.update(tip,new T.Vector3(),new T.Vector3(0,-1,0),i/30,true);
    const pos=line.object.geometry.attributes.position,center=new T.Vector3();for(let j=0;j<5;j++)center.add(new T.Vector3().fromBufferAttribute(pos,j));center.multiplyScalar(.2);
    assert(center.distanceTo(tip)<1e-6,'free line detached from mounted tip');line.dispose();
   }
   for(const side of ['Right','Left']) {
    const hand=by.get(side+'Hand');
    const elbow=by.get(side+'ForeArm').getWorldPosition(new T.Vector3());
    const shoulder=by.get(side+'Arm').getWorldPosition(new T.Vector3());
    assert(Math.hypot(elbow.x/(sex==='Male'?.205:.185),elbow.z/.18)>1.20,`${sex} ${side} elbow entered torso clearance envelope`);
    assert(Math.abs(elbow.x)>Math.abs(shoulder.x)-.015,'upper arm crosses inward through chest');
    assert(elbow.y<shoulder.y-.10,`${sex} ${side} elbow lifted toward the shoulder`);
    assert(elbow.y<hand.getWorldPosition(new T.Vector3()).y+.002,`${sex} ${side} elbow above the hand`);
    const bend=rest.get(hand.name).q.angleTo(hand.quaternion);
    maximumWristBend=Math.max(maximumWristBend,bend);
    assert(bend<20*Math.PI/180,`${sex} fishing wrist overextends at ${i/30}s`);
   }
  }
 }
 assert(worst<.003,`${sex} ${kind} feet slide ${worst}`);
 action.time=.5;mixer.update(0);const a=by.get('RightHand').getWorldQuaternion(new T.Quaternion());action.time=1;mixer.update(0);assert(a.angleTo(by.get('RightHand').getWorldQuaternion(new T.Quaternion()))>.001,'paused seek must change pose');
 report.animations.push({sex,kind,frames:spec.tracks[0].keyframes.length,maximumFootDriftMetres:worst,...(kind==='Fishing'?{maximumWristBendDegrees:maximumWristBend*180/Math.PI}:{})});mixer.stopAllAction();mixer.uncacheRoot(root);
}
// Exercise the unchanged shared locomotion clips with the rod-specific carry transform.
report.carry=[];
for(const sex of ['Female','Male'])for(const name of ['Idle','Walk','WalkV2','WalkV3','Run','RunV2','RunV3']) {
 const spec=JSON.parse(fs.readFileSync(`${P}/animations/Female${name}.anim.json`));
 const {root,by,rest}=rig(sex);root.rotation.x=Math.PI/2;root.updateMatrixWorld(true);
 const resting=new Map([...rest].map(([n,v])=>[n,{position:v.p,quaternion:v.q}]));
 const mixer=new T.AnimationMixer(root),action=mixer.clipAction(animSpecToClip(spec,resting,.01/by.get('Hips').parent.getWorldScale(new T.Vector3()).y));action.play();action.paused=true;
 let ground=Infinity;
 const rods=Object.entries(rodData).map(([id,anchor])=>{const model=new T.Group();for(const [name,p]of [['FishingGrip',anchor.grip],['FishingTip',anchor.tip]]){const n=new T.Object3D();n.name=name;n.position.fromArray(p);model.add(n)}return {id,anchor,model,carry:createFishingCarryMount(model)}});
 for(let i=0;i<=60;i++){
  action.time=spec.meta.duration*i/60;mixer.update(0);root.updateMatrixWorld(true);
  const h=by.get('RightHand'),q=h.getWorldQuaternion(new T.Quaternion()),hp=h.getWorldPosition(new T.Vector3());
  const right=by.get('RightArm').getWorldPosition(new T.Vector3()).sub(by.get('LeftArm').getWorldPosition(new T.Vector3()));right.z=0;right.normalize();
  for(const {anchor,carry,model}of rods){
   const mounted=carry(q,right),matrix=new T.Matrix4().compose(hp,q,new T.Vector3(1,1,1)).multiply(new T.Matrix4().compose(mounted.position,mounted.quaternion,new T.Vector3(1,1,1)));
   const grip=new T.Vector3(...anchor.grip).addScaledVector(new T.Vector3(...anchor.tip).sub(new T.Vector3(...anchor.grip)).normalize(),.055).applyMatrix4(matrix),palm=new T.Vector3(0,.095,.050).applyQuaternion(q).add(hp);
   assert(grip.distanceTo(palm)<1e-6,'carry handle escaped palm');
   const group=new T.Group();matrix.decompose(group.position,group.quaternion,group.scale);group.add(model);group.updateMatrixWorld(true);
   const before=new Map([...by.values()].map(b=>[b,b.quaternion.clone()]));
   const contact=createFishingGrip();contact.apply(new Map([...by.values()].map(b=>[b.name,b])),model);
   for(const [bone,q]of before){assert(bone.quaternion.toArray().every(Number.isFinite));if(!/RightHand(Index|Middle|Ring|Pinky|Thumb)[123]$/.test(bone.name))assert(bone.quaternion.equals(q),'grip changed shared body motion');}
   contact.restore();for(const [bone,q]of before)assert(bone.quaternion.equals(q),'grip did not restore original fingers');
   root.updateMatrixWorld(true);

   const tip=new T.Vector3(...anchor.tip).applyMatrix4(matrix);assert(tip.z>grip.z+.15,'carry rod slopes toward ground');
   for(const p of [anchor.grip,...anchor.guide_points])ground=Math.min(ground,new T.Vector3(...p).applyMatrix4(matrix).z);
  }
 }
 assert(ground>.25,`${sex} ${name} rod reaches ground`);report.carry.push({sex,animation:name,minimumShaftHeight:ground});mixer.stopAllAction();mixer.uncacheRoot(root);
}
for(const filename of fs.readdirSync(`${P}/tools/fishing_rods`).filter(f=>f.endsWith('.glb'))) {
 const b=fs.readFileSync(`${P}/tools/fishing_rods/${filename}`),g=JSON.parse(b.subarray(20,20+b.readUInt32LE(12)));
 assert.equal(g.nodes.filter(n=>n.name==='FishingGrip').length,1);assert.equal(g.nodes.filter(n=>n.name==='FishingTip').length,1);const anchor=rodData[filename.slice(0,-4)];assert.deepEqual(anchor.tip,anchor.guide_points.at(-1),'guide string and free line must meet');assert.equal(g.nodes.filter(n=>n.name==='FishingLineGuides').length,1);
 const node=g.nodes.find(n=>n.name==='FishingLineGuides'),mesh=g.meshes[node.mesh];assert(mesh.primitives.length>0);report.rods.push(filename);
}
assert.equal(report.rods.length,8);
const tip=new T.Vector3(.1,.7,1.5),origin=new T.Vector3(),forward=new T.Vector3(0,1,0),line=createFishingLine();
const pos=line.object.geometry.attributes.position,arr=pos.array;
function center(ring){const p=new T.Vector3();for(let j=0;j<5;j++)p.add(new T.Vector3().fromBufferAttribute(pos,ring*5+j));return p.multiplyScalar(.2);}
for(let i=0;i<=600;i++) {line.update(tip,origin,forward,i/60,true);assert(pos.array===arr);assert(arr.every(Number.isFinite));assert(center(0).distanceTo(tip)<1e-6);}
line.update(tip,origin,forward,4,true);assert(center(40).distanceTo(new T.Vector3(0,1.5,.025))<1e-6);
line.update(tip,origin,forward,0,true);const initial=arr.slice();line.update(tip,origin,forward,10,true);assert.deepEqual(arr,initial);
let disposed=0;line.object.geometry.addEventListener('dispose',()=>disposed++);line.object.material.addEventListener('dispose',()=>disposed++);line.dispose();assert.equal(disposed,2);
for(const [id,style]of Object.entries(SPELL_STYLES)) {
 const effect=createSpellEffect(style),buffers=effect.object.children.flatMap(o=>Object.values(o.geometry.attributes).map(a=>a.array));
 for(let i=0;i<168;i++) {effect.update(tip,origin,forward,i/60,true);for(const a of buffers)assert(a.every(Number.isFinite));}
 effect.update(tip,origin,forward,1,true);assert(effect.object.visible);assert.equal(effect.object.children.length,4);
 effect.update(tip,origin,forward,2,true);assert(!effect.object.visible);effect.update(tip,origin,forward,1,false);assert(!effect.object.visible);
 let disposed=0;effect.object.children.forEach(o=>{o.geometry.addEventListener('dispose',()=>disposed++);o.material.addEventListener('dispose',()=>disposed++);});effect.dispose();assert.equal(disposed,8);report.spells.push({id,drawCalls:4,particles:96});
}
console.log(JSON.stringify(report,null,2));
