import * as T from 'three';

/** Temporary finger-only contact pose. Restore before the next mixer update or unequip. */
export function createFishingGrip() {
  const saved = new Map<T.Bone,T.Quaternion>();
  const restore = () => { for (const [bone,q] of saved) bone.quaternion.copy(q); saved.clear(); };
  const pos = (b:T.Object3D) => b.getWorldPosition(new T.Vector3());
  const worldQ = (b:T.Object3D,q:T.Quaternion) => {
    b.quaternion.copy(b.parent!.getWorldQuaternion(new T.Quaternion()).invert().multiply(q));
    b.updateWorldMatrix(false,true);
  };
  const aim = (b:T.Object3D,child:T.Object3D,target:T.Vector3) => {
    const origin=pos(b);
    worldQ(b,new T.Quaternion().setFromUnitVectors(pos(child).sub(origin).normalize(),target.clone().sub(origin).normalize()).multiply(b.getWorldQuaternion(new T.Quaternion())));
  };
  const ik = (a:T.Object3D,b:T.Object3D,c:T.Object3D,target:T.Vector3,pole:T.Vector3) => {
    const A=pos(a),l1=A.distanceTo(pos(b)),l2=pos(b).distanceTo(pos(c)),dir=target.clone().sub(A);
    const d=Math.max(.0001,Math.min(dir.length(),(l1+l2)*.995));dir.normalize();
    const plane=pole.clone().sub(A);plane.addScaledVector(dir,-plane.dot(dir)).normalize();
    const along=(l1*l1-l2*l2+d*d)/(2*d);
    aim(a,b,A.clone().addScaledVector(dir,along).addScaledVector(plane,Math.sqrt(Math.max(0,l1*l1-along*along))));
    aim(b,c,A.clone().addScaledVector(dir,d));
  };
  const apply = (bones:Map<string,T.Bone>,model:T.Object3D) => {
    const hand=bones.get('mixamorigRightHand'),grip=model.getObjectByName('FishingGrip'),tip=model.getObjectByName('FishingTip');
    if(!hand || !grip || !tip)return;
    model.updateWorldMatrix(true,true);
    const center=pos(grip),axis=pos(tip).sub(center).normalize();center.addScaledVector(axis,.055);
    const palmNormal=new T.Vector3(0,0,1).applyQuaternion(hand.getWorldQuaternion(new T.Quaternion()));
    for(const finger of ['Index','Middle','Ring','Pinky','Thumb']) {
      const chain=[1,2,3,4].map(i=>bones.get(`mixamorigRightHand${finger}${i}`));
      if(chain.some(b=>!b))continue;
      const [a,b,c,end]=chain as T.Bone[];
      for(const bone of [a,b,c])saved.set(bone,bone.quaternion.clone());
      const start=pos(a),contact=center.clone().addScaledVector(axis,start.clone().sub(center).dot(axis));
      const radial=start.clone().sub(contact).addScaledVector(axis,-start.clone().sub(contact).dot(axis)).normalize();
      const bend=radial.clone().cross(axis).normalize();if(bend.dot(palmNormal)<0)bend.negate();
      const target=contact.clone().addScaledVector(radial,.018).addScaledVector(bend,.010);
      ik(a,b,c,target,pos(b).addScaledVector(bend,.015));
      aim(c,end,contact.clone().addScaledVector(radial,-.009).addScaledVector(bend,.018));
    }
    hand.updateWorldMatrix(false,true);
  };
  return {restore,apply};
}
