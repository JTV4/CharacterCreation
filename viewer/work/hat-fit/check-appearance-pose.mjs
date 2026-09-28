import fs from 'node:fs';
import assert from 'node:assert/strict';
import ts from 'typescript';
import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
fs.writeFileSync('work/hat-fit/appearancePose.generated.mjs',ts.transpileModule(fs.readFileSync('src/utils/appearancePose.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText);
const {appearancePosePairs,syncAppearancePose}=await import('./appearancePose.generated.mjs');
globalThis.ProgressEvent=class ProgressEvent {};
async function load(path){
 const b=fs.readFileSync(path), n=b.readUInt32LE(12), j=JSON.parse(b.subarray(20,20+n)),start=20+n;
 j.buffers[0].uri='data:application/octet-stream;base64,'+b.subarray(start+8,start+8+b.readUInt32LE(start)).toString('base64');
 delete j.images; delete j.textures; delete j.materials;
 for(const m of j.meshes)for(const p of m.primitives)delete p.material;
 return (await new GLTFLoader().parseAsync(JSON.stringify(j),'' )).scene;
}
let checked=0, ancestorCount=0;
for(const sex of ['Male','Female']){
 const body=await load(`public/appearance/v6/Models/Base${sex}_Appearance.glb`), bones=new Map();
 body.traverse(o=>{if(o.isBone)bones.set(o.name,o)});
 body.rotation.x=Math.PI/2;body.scale.setScalar(1.9/1.75);
 for(const name of ['Hips','Spine','Spine1','Spine2','Neck','Head']){
  const b=bones.get('mixamorig'+name); b.rotation.z+=.15;b.rotation.x+=.12;
 }
 bones.get('mixamorigHips').position.x+=.2;body.updateMatrixWorld(true);
 for(const folder of ['Hair','FacialHair','Face']){
  const dir=`public/appearance/v6/Models/${folder}`;if(!fs.existsSync(dir))continue;
  for(const name of fs.readdirSync(dir).filter(n=>n.startsWith(sex+'_')&&n.endsWith('.glb'))){
   const accessory=await load(dir+'/'+name),pairs=appearancePosePairs(accessory,bones);
   ancestorCount+=pairs.filter(([target])=>!target.isBone).length;
   syncAppearancePose(accessory,body,pairs);
   for(const [target,source] of pairs){
    const error=Math.max(...target.matrixWorld.elements.map((v,i)=>Math.abs(v-source.matrixWorld.elements[i])));
    assert(error<2e-6,`${name} ${target.name} error ${error}`);
   }
   assert(pairs.length>=6,`${name} ancestor chain missing`);checked++;
  }
 }
}
console.log(`PASS: ${checked} appearance assets; ${ancestorCount} non-Bone ancestor transforms synchronized.`);
