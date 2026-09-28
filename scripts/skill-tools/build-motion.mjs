import fs from 'node:fs';
import {T,P,rig} from './rig.mjs';
const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*x*(x*(x*6-15)+10)};
function sample(keys,t){let i=keys.findIndex(k=>k[0]>=t);if(i<0)i=keys.length-1;const a=keys[Math.max(0,i-1)],b=keys[i],f=smooth(b[0]===a[0]?0:(t-a[0])/(b[0]-a[0]));return a.slice(1).map((v,j)=>v+(b[j+1]-v)*f)}
const q=new T.Quaternion(),v=new T.Vector3();
for(const sex of ['Female','Male']){
 const r=rig(sex),{root,bones,by,rest}=r;
 const pos=b=>b.getWorldPosition(new T.Vector3());
 const worldQ=(b,rotation)=>{b.quaternion.copy(b.parent.getWorldQuaternion(new T.Quaternion()).invert().multiply(rotation));root.updateMatrixWorld(true)};
 function aim(b,child,target){const origin=pos(b),from=pos(child).sub(origin).normalize(),to=target.clone().sub(origin).normalize();worldQ(b,new T.Quaternion().setFromUnitVectors(from,to).multiply(b.getWorldQuaternion(new T.Quaternion())))}
 function ik(a,b,c,target,pole,reach=.995){const A=pos(a),l1=A.distanceTo(pos(b)),l2=pos(b).distanceTo(pos(c)),dir=target.clone().sub(A),d=Math.min(dir.length(),(l1+l2)*reach);dir.normalize();const plane=pole.clone().sub(A);plane.addScaledVector(dir,-plane.dot(dir)).normalize();const along=(l1*l1-l2*l2+d*d)/(2*d);const E=A.clone().addScaledVector(dir,along).addScaledVector(plane,Math.sqrt(Math.max(0,l1*l1-along*along)));aim(a,b,E);aim(b,c,A.clone().addScaledVector(dir,d))}
 const feet=['Left','Right'].map(s=>({side:s,target:pos(by.get(s+'Foot')),q:by.get(s+'Foot').getWorldQuaternion(new T.Quaternion())}));
 for(const kind of ['Fishing','MagicCast']){
  const duration=kind==='Fishing'?10:2.8,tracks=new Map(bones.map(b=>[b.name,[]])),hips=[];
  for(let frame=0;frame<=duration*30;frame++){
   const t=frame/30;for(const b of bones){b.position.copy(rest.get(b.name).p);b.quaternion.copy(rest.get(b.name).q)}root.updateMatrixWorld(true);
   const fishing=kind==='Fishing';
   const phase=fishing?sample([[0,0],[.8,0],[1.55,1],[2.35,0],[7.2,0],[8.25,.65],[9.4,0],[10,0]],t)[0]:sample([[0,0],[.3,0],[.68,1],[.9,-.6],[1.3,-.15],[2,0],[2.8,0]],t)[0];
   const breath=Math.sin(t/duration*Math.PI*2);
   const hip=by.get('Hips'),scale=hip.parent.getWorldScale(new T.Vector3()).y;
   hip.position.add(new T.Vector3(.006*breath,-(fishing?.040:.012)-.008*Math.abs(phase),.008*phase).applyQuaternion(hip.parent.getWorldQuaternion(new T.Quaternion()).invert()).multiplyScalar(1/scale));root.updateMatrixWorld(true);
   for(const [name,angle]of [['Spine',(fishing?.045:0)+.025*phase],['Spine1',(fishing?.04:0)+.018*phase],['Spine2',(fishing?.025:0)+.012*phase],['Head',-.022*phase]]){const b=by.get(name);b.quaternion.multiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),angle));}root.updateMatrixWorld(true);
   for(const f of feet){const target=f.target.clone();if(fishing)target.x+=Math.sign(target.x)*.05;ik(by.get(f.side+'UpLeg'),by.get(f.side+'Leg'),by.get(f.side+'Foot'),target,new T.Vector3(target.x, .6,.5),.99999);worldQ(by.get(f.side+'Foot'),f.q)}
   const rt=fishing?new T.Vector3(-.20,1.25+.045*phase+.003*breath,.22-.055*phase):new T.Vector3(...sample([[0,-.23,1.23,.18],[.3,-.23,1.23,.18],[.68,-.26,1.34,.08],[.9,-.20,1.29,.28],[1.35,-.20,1.29,.28],[2.2,-.23,1.23,.18],[2.8,-.23,1.23,.18]],t));
   const lt=fishing?new T.Vector3(.23,1.09+.008*phase,.10):new T.Vector3(.22,1.24+.05*phase,.22+.04*phase);
   for(const [side,target]of [['Right',rt],['Left',lt]]){const sign=side==='Right'?-1:1;ik(by.get(side+'Arm'),by.get(side+'ForeArm'),by.get(side+'Hand'),target,new T.Vector3(sign*.58,1.03,.03))}
   if (fishing) {
    // Both hands hold the forward handle; the rod pitches up while the feet stay fixed.
    const pitch=.78+.10*phase;
    const shaft=new T.Vector3(0,Math.sin(pitch),Math.cos(pitch));
    const grip=new T.Vector3(0,(sex==='Male'?1.27:1.285)+.014*phase,sex==='Male'?.315:.300);
    for(const side of ['Right','Left']){
     const sign=side==='Right'?1:-1;
     const diagonal=.55,inward=.9;
     const across=new T.Vector3(sign*inward,-Math.cos(pitch)*Math.sqrt(1-inward*inward),Math.sin(pitch)*Math.sqrt(1-inward*inward));
     const x=shaft.clone().multiplyScalar(sign*Math.cos(diagonal)).addScaledVector(across,-sign*Math.sin(diagonal));
     const y=shaft.clone().multiplyScalar(Math.sin(diagonal)).addScaledVector(across,Math.cos(diagonal));
     const z=new T.Vector3().crossVectors(x,y);
     const desired=new T.Quaternion().setFromRotationMatrix(new T.Matrix4().makeBasis(x,y,z));
     const center=grip.clone().addScaledVector(shaft,side==='Left'?.10:0);
     const wrist=center.clone().sub(new T.Vector3(0,.105,.024).applyQuaternion(desired));
     const arm=by.get(side+'Arm'),forearm=by.get(side+'ForeArm'),hand=by.get(side+'Hand');
     // Keep the elbow on the outside of the torso; a hand-derived pole folds it inward.
     const pole=new T.Vector3(-sign*.85,.70,.02);
     ik(arm,forearm,hand,wrist,pole);
     // Roll about the forearm, then use only the small remaining wrist correction.
     const axis=pos(hand).sub(pos(forearm)).normalize();
     const current=new T.Vector3(0,0,1).applyQuaternion(hand.getWorldQuaternion(new T.Quaternion()));
     const target=z.clone();current.addScaledVector(axis,-current.dot(axis)).normalize();target.addScaledVector(axis,-target.dot(axis)).normalize();
     worldQ(forearm,new T.Quaternion().setFromUnitVectors(current,target).multiply(forearm.getWorldQuaternion(new T.Quaternion())));
     worldQ(hand,desired);
    }
   } else {
    const tilt=.83+phase*.16;
    const d=new T.Vector3(.05,Math.sin(tilt),Math.cos(tilt)).normalize();
    const hand=by.get('RightHand'),restWorld=rest.get(hand.name).world,restX=new T.Vector3(1,0,0).applyQuaternion(restWorld);
    worldQ(hand,new T.Quaternion().setFromUnitVectors(restX,d).multiply(restWorld));
   }
   // Curl the gripping fingers, leaving the off-hand relaxed for line control / channeling.
   for(const side of ['Right','Left'])for(const finger of ['Index','Middle','Ring','Pinky'])for(let j=1;j<=3;j++){
    const b=by.get(`${side}Hand${finger}${j}`);if(!b)continue;const curl=fishing || side==='Right'?(j===1?.78:1.04):.18;b.quaternion.multiply(new T.Quaternion().setFromAxisAngle(new T.Vector3(1,0,0),curl));
   }
   if(fishing){
    for(const side of ['Right','Left']){
     const sign=side==='Right'?1:-1;
     const hand=by.get(side+'Hand'),hq=hand.getWorldQuaternion(new T.Quaternion()),hp=pos(hand);
     const point=(x,y,z)=>new T.Vector3(sign*x,y,z).applyQuaternion(hq).add(hp);
     const handle=new T.Vector3(0,.105,.024),axis=new T.Vector3(sign*Math.cos(.55),Math.sin(.55),0),across=new T.Vector3(-sign*Math.sin(.55),Math.cos(.55),0);
     for(const finger of ['Index','Middle','Ring','Pinky']){
      const b1=by.get(side+'Hand'+finger+'1'),b2=by.get(side+'Hand'+finger+'2'),b3=by.get(side+'Hand'+finger+'3'),end=by.get(side+'Hand'+finger+'4');
      const start=pos(b1).sub(hp).applyQuaternion(hq.clone().invert());
      const center=handle.clone().addScaledVector(axis,start.clone().sub(handle).dot(axis));
      const local3=center.clone().addScaledVector(across,.020);local3.z+=.020;
      const localTip=center.clone().addScaledVector(across,.005);localTip.z+=.018;
      const goal3=local3.applyQuaternion(hq).add(hp),goalTip=localTip.applyQuaternion(hq).add(hp),pole=pos(b2);
      ik(b1,b2,b3,goal3,pole);aim(b3,end,goalTip);
     }
     const thumb1=by.get(side+'HandThumb1'),thumb2=by.get(side+'HandThumb2'),thumb3=by.get(side+'HandThumb3');
     ik(thumb1,thumb2,thumb3,point(.043,.102,.043),point(.082,.070,.015));
     aim(thumb3,by.get(side+'HandThumb4'),point(.018,.106,.039));
    }
   }
   root.updateMatrixWorld(true);
   for(const b of bones){const delta=rest.get(b.name).q.clone().invert().multiply(b.quaternion).normalize();const keys=tracks.get(b.name);if(keys.length&&new T.Quaternion().fromArray(keys.at(-1).value).dot(delta)<0)delta.set(-delta.x,-delta.y,-delta.z,-delta.w);keys.push({time:t,value:delta.toArray().map(n=>+n.toFixed(7))})}
   const hp=hip.position.clone().sub(rest.get(hip.name).p).multiplyScalar(scale*100);hips.push({time:t,value:hp.toArray().map(n=>+n.toFixed(5))});
  }
  const spec={meta:{id:'Female'+kind,name:sex+kind,duration,fps:30,loop:true},tracks:[...tracks].map(([bone,keyframes])=>({bone,property:'rotation',interpolation:'linear',keyframes}))};spec.tracks.push({bone:'mixamorigHips',property:'position',interpolation:'linear',keyframes:hips});
  const file=`${sex}${kind}.anim.json`;fs.writeFileSync(`${P}/animations/${file}`,JSON.stringify(spec));
 }
}
