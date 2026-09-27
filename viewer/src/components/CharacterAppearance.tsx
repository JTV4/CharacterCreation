import FacialHair from './FacialHair';
import FacialFeatures from './FacialFeatures';
import {useEffect,useRef,useState} from 'react';
import {useFrame} from '@react-three/fiber';
import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import type {CharacterModel} from '../types';
import type {AppearanceSex,AppearanceOptions} from './AppearancePanel';
import palette from '../data/appearance.json';
const base='/appearance/v6/';
const textures=new Map<string,Promise<THREE.Texture>>();
function eyeTexture(path:string){if(!textures.has(path))textures.set(path,new THREE.TextureLoader().loadAsync(base+path+'?v=eyes-20260927').then(t=>{t.colorSpace=THREE.SRGBColorSpace;t.flipY=false;return t}).catch(e=>{textures.delete(path);throw e}));return textures.get(path)!;}
function disposeHair(root:THREE.Object3D){root.traverse(o=>{if(o instanceof THREE.Mesh){o.geometry.dispose();[].concat(o.material as any).forEach((m:THREE.Material)=>m.dispose());}if(o instanceof THREE.SkinnedMesh)o.skeleton.dispose();});}
export default function CharacterAppearance({model,sex,value,visible,hideHair=false,onError}:{model:CharacterModel;sex:AppearanceSex;value:AppearanceOptions;visible:boolean;hideHair?:boolean;onError:(error:string|null)=>void}){
 const [hair,setHair]=useState<THREE.Group|null>(null);
 const gaze=useRef({x:0,y:0,items:[] as {uv:THREE.BufferAttribute|THREE.InterleavedBufferAttribute;base:Float32Array}[]});
 const hairColor=palette.hairColors.find(x=>x.id===value.hairColor)!.color;
 useEffect(()=>{const items:typeof gaze.current.items=[];model.scene.traverse(o=>{if(o instanceof THREE.Mesh&&[].concat(o.material as any).some((m:THREE.Material)=>m.name==='GS_Eyes')){const uv=o.geometry.attributes.uv;items.push({uv,base:Float32Array.from({length:uv.count*2},(_,i)=>i%2?uv.getY(Math.floor(i/2)):uv.getX(Math.floor(i/2)))});}});gaze.current={x:0,y:0,items};return()=>{for(const {uv,base}of items){for(let i=0;i<uv.count;i++)uv.setXY(i,base[i*2],base[i*2+1]);uv.needsUpdate=true;}};},[model]);
 useEffect(()=>{const tone=palette.skinTones.find(x=>x.id===value.skin)!;model.scene.traverse(o=>{if(o instanceof THREE.Mesh)for(const raw of [].concat(o.material as any)){const m=raw as THREE.MeshStandardMaterial;if(m.name==='GS_Skin'){m.map=null;m.color.set(tone.color);m.vertexColors=!!o.geometry.getAttribute('color');m.transparent=false;m.opacity=1;m.depthWrite=true;m.needsUpdate=true;}}});},[model,value.skin]);
 useEffect(()=>{let cancelled=false;const option=palette.eyes.find(x=>x.id===value.eyes)!;eyeTexture(option.texture).then(t=>{if(cancelled)return;model.scene.traverse(o=>{if(o instanceof THREE.Mesh)for(const raw of [].concat(o.material as any)){const m=raw as THREE.MeshStandardMaterial;if(m.name==='GS_Eyes'){m.map=t;m.color.set('white');m.needsUpdate=true;}}});}).catch(e=>{if(!cancelled)onError('Eye texture could not load: '+e.message)});return()=>{cancelled=true};},[model,value.eyes,onError]);
 useEffect(()=>{let cancelled=false;let owned:THREE.Group|null=null;setHair(null);onError(null);if(value.hair==='none')return;
 new GLTFLoader().loadAsync(base+'Models/Hair/'+sex+'_'+value.hair+'.glb?v=hairline-20260927-v4').then(g=>{if(cancelled){disposeHair(g.scene);return;}owned=g.scene;g.scene.traverse(o=>{if(o instanceof THREE.SkinnedMesh)o.frustumCulled=false;});setHair(g.scene);}).catch(e=>{if(!cancelled)onError('Hair could not load: '+e.message)});
 return()=>{cancelled=true;if(owned)disposeHair(owned);};},[model,sex,value.hair,onError]);
 useEffect(()=>{hair?.traverse(o=>{if(o instanceof THREE.Mesh)for(const m of [].concat(o.material as any))(m as THREE.MeshStandardMaterial).color.set(hairColor);});},[hair,hairColor]);
 useFrame((state,delta)=>{
 const g=gaze.current,a=1-Math.exp(-9*delta);const x=value.demo?Math.sin(state.clock.elapsedTime*.8):value.gazeX,y=value.demo?.7*Math.sin(state.clock.elapsedTime*.53):value.gazeY;g.x+=(x-g.x)*a;g.y+=(y-g.y)*a;
 // Eye UVs use equal physical scale; limit vertical travel beneath the fixed eyelids.
 for(const {uv,base}of g.items){for(let i=0;i<uv.count;i++)uv.setXY(i,base[i*2]-g.x*.095,base[i*2+1]+g.y*.06);uv.needsUpdate=true;}
 if(hair){hair.position.copy(model.scene.position);hair.quaternion.copy(model.scene.quaternion);hair.scale.copy(model.scene.scale);hair.traverse(o=>{if(o instanceof THREE.Bone){const b=model.boneObjMap.get(o.name);if(b){o.position.copy(b.position);o.quaternion.copy(b.quaternion);o.scale.copy(b.scale);}}});hair.updateMatrixWorld(true);}
 });
 return <>
 {hair&&<primitive object={hair} visible={visible && !hideHair} dispose={null}/>}
    <FacialHair model={model} sex={sex} kind="Beard" style={value.beardStyle} color={hairColor} visible={visible} onError={onError}/>
    <FacialHair model={model} sex={sex} kind="Mustache" style={value.mustacheStyle} color={hairColor} visible={visible} onError={onError}/>
    <FacialFeatures model={model} sex={sex} eyebrowStyle={value.eyebrowStyle} eyelashStyle={value.eyelashStyle} color={hairColor} visible={visible} onError={onError}/>
 </>;
}
