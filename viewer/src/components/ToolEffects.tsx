import { useEffect, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as T from 'three';
import type { AnimationPlayerState } from '../hooks/useAnimationPlayer';
import type { ToolDefinition } from '../types/tools';
import anchors from '../data/toolEffectAnchors.json';
import { createFishingLine, createSpellEffect, SPELL_STYLES } from '../utils/toolEffects';

export default function ToolEffects({ tool, model, playerRef, detached, syncAttachment }: {
  tool: ToolDefinition; model: T.Object3D; playerRef: React.MutableRefObject<AnimationPlayerState | null>; detached: boolean; syncAttachment: () => void;
}) {
  const fishing = tool.category === 'fishing_rods';
  const effect = useMemo(() => fishing ? createFishingLine() : SPELL_STYLES[tool.id] ? createSpellEffect(SPELL_STYLES[tool.id]) : null, [tool.id, fishing]);
  const scratch = useMemo(() => ({ tip: new T.Vector3(), origin: new T.Vector3(), forward: new T.Vector3(), foot: new T.Vector3(), toe: new T.Vector3() }), []);
  const tipNode = useMemo(() => model.getObjectByName('FishingTip'), [model]);
  const localTip = useMemo(() => {
    const filename = tool.url.split('/').pop()!.split('.')[0];
    return new T.Vector3(...((anchors as Record<string, number[]>)[filename] ?? [.8, .1, 0]) as [number, number, number]);
  }, [tool.url]);
  useEffect(() => () => effect?.dispose(), [effect]);
  useFrame(() => {
    if (!effect) return;
    const player = playerRef.current;
    effect.object.visible = !!player && !detached;
    if (!player || detached) return;
    // Sample the tip only after the hand attachment has its current-frame pose.
    syncAttachment();
    model.updateWorldMatrix(true, true);
    if (tipNode) tipNode.getWorldPosition(scratch.tip); else scratch.tip.copy(localTip).applyMatrix4(model.matrixWorld);
    const bone = (name: string) => player.boneObjMap.get('mixamorig' + name) ?? player.boneObjMap.get('mixamorig:' + name);
    const hip = bone('Hips'); if (!hip) return;
    hip.getWorldPosition(scratch.origin); scratch.origin.z = 0;
    scratch.forward.set(0, 0, 0);
    for (const side of ['Left', 'Right']) {
      const foot = bone(side + 'Foot'), toe = bone(side + 'ToeBase');
      if (foot && toe) { toe.getWorldPosition(scratch.toe); foot.getWorldPosition(scratch.foot); scratch.forward.add(scratch.toe.sub(scratch.foot)); }
    }
    scratch.forward.z = 0; if (scratch.forward.lengthSq() < .001) scratch.forward.set(0, 1, 0); scratch.forward.normalize();
    const active = fishing ? /Fishing$/.test(player.activeAnimId ?? '') : /MagicCast$/.test(player.activeAnimId ?? '');
    effect.update(scratch.tip, scratch.origin, scratch.forward, player.getTime(), active);
  });
  return effect ? <primitive object={effect.object} /> : null;
}
