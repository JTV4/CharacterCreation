import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import ts from 'typescript';
import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
const V=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const url=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
const compile=name=>ts.transpileModule(fs.readFileSync(path.join(V,'src/utils',name),'utf8'),{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText.replaceAll('"three"',JSON.stringify(pathToFileURL(path.join(V,'node_modules/three/build/three.module.js')).href)).replaceAll("'three'",JSON.stringify(pathToFileURL(path.join(V,'node_modules/three/build/three.module.js')).href));
const {createCapeMotion}=await import(url(compile('capeMotion.ts').replace('"./capeGravity"',JSON.stringify(url(compile('capeGravity.ts'))))));
const {createCapeSparkles}=await import(url(compile('capeSparkles.ts')));
const spec=JSON.parse(fs.readFileSync(path.join(V,'public/equipment/equipment_spec_seasonal_capes.json')));assert.equal(spec.slots.length,6);const results=[];
for(const slot of spec.slots){
 assert.equal(slot.wear_slot,'cape');assert.equal(slot.hides_hair,false);
 const bytes=fs.readFileSync(path.join(V,'public',slot.url.split('?')[0]));assert(bytes.length<1200000);
 const gltf=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');gltf.scene.updateMatrixWorld(true);
 let triangles=0,sparkle;const materials=new Set();
 gltf.scene.traverse(o=>{if(!o.isSkinnedMesh)return;const g=o.geometry;triangles+=(g.index?.count??g.attributes.position.count)/3;
  const p=g.attributes.position,w=g.attributes.skinWeight,j=g.attributes.skinIndex;assert(w&&j);
  for(let i=0;i<p.count;i++){let sum=0;for(let k=0;k<4;k++){const weight=w.getComponent(i,k);assert(weight>=0&&weight<=1.0001);sum+=weight;if(weight>0)assert(j.getComponent(i,k)<o.skeleton.bones.length);}assert(Math.abs(sum-1)<.0002);assert([p.getX(i),p.getY(i),p.getZ(i)].every(Number.isFinite));}
  for(const m of [].concat(o.material)){materials.add(m);assert(!m.transparent&&m.opacity===1);if(m.name.startsWith('SeasonalSparkle '))sparkle=m;}
 });assert(triangles<=15000);assert(materials.size<=8);assert(sparkle);
 assert.deepEqual(gltf.animations.map(a=>a.name).sort(),['Cape_Idle','Cape_Run','Cape_Walk']);
 assert(gltf.animations.every(a=>a.tracks.length===38&&a.tracks.every(t=>t.name.startsWith('Cape_'))));
 const motion=createCapeMotion(gltf.scene,gltf.animations);assert(motion);const glitter=createCapeSparkles(gltf.scene);assert(glitter);
 const points=gltf.scene.getObjectByName('Seasonal cape sparkles');assert(points?.isPoints);assert.equal(points.geometry.attributes.position.count,32);
 assert.equal(points.material.depthTest,true);assert.equal(points.material.depthWrite,false);assert.equal(points.material.blending,THREE.AdditiveBlending);
 const initial=Array.from(points.geometry.attributes.position.array);let disposedGeometry=false,disposedMaterial=false;
 points.geometry.addEventListener('dispose',()=>disposedGeometry=true);points.material.addEventListener('dispose',()=>disposedMaterial=true);
 const originalKey=sparkle.customProgramCacheKey();const shader={uniforms:{},vertexShader:'#include <begin_vertex>',fragmentShader:'#include <emissivemap_fragment>'};sparkle.onBeforeCompile(shader,{});
 assert(shader.vertexShader.includes('capeSparklePhase ='));assert(shader.fragmentShader.includes('totalEmissiveRadiance *= '));assert(shader.uniforms.capeSparkleTime);
 const start=performance.now();for(let i=0;i<240;i++){motion.update(1/60,i<120?0:1);glitter.update(1/60)}const ms=(performance.now()-start)/240;
 assert([...points.geometry.attributes.position.array].every(Number.isFinite));assert.notDeepEqual(Array.from(points.geometry.attributes.position.array),initial);
 assert(shader.uniforms.capeSparkleTime.value>3.9);const time=shader.uniforms.capeSparkleTime.value;glitter.update(NaN);glitter.update(-1);assert.equal(shader.uniforms.capeSparkleTime.value,time);
 gltf.scene.traverse(o=>assert([...o.position,...o.quaternion,...o.scale].every(Number.isFinite)));
 glitter.dispose();glitter.dispose();assert(disposedGeometry&&disposedMaterial);assert.equal(points.parent,null);glitter.update(1);assert.equal(shader.uniforms.capeSparkleTime.value,time);assert.notEqual(sparkle.customProgramCacheKey(),originalKey);motion.dispose();
 results.push({id:slot.id,bytes:bytes.length,triangles,materials:materials.size,cpuMillisecondsPerUpdate:ms});
}
console.log(JSON.stringify({valid:true,assets:results},null,2));
