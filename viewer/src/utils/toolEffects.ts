import * as T from 'three';

export const SPELL_STYLES: Record<string, { name: string; color: string; accent: string; shape: string }> = {
  topaz_staff: { name: 'Static Shock', color: '#ffdd55', accent: '#fff4bb', shape: 'bolt' },
  spinel_staff: { name: 'Chakra Blast', color: '#a464ff', accent: '#eac9ff', shape: 'helix' },
  peridot_staff: { name: 'Blitz', color: '#38dfff', accent: '#dcffff', shape: 'lance' },
  ruby_staff: { name: 'Heart Breaker', color: '#fa52a4', accent: '#ffe3f3', shape: 'petals' },
  rubellite_staff: { name: 'Scarlet Scorch', color: '#ef3150', accent: '#ffaf73', shape: 'ember' },
  enchanted_staff: { name: 'Enchanted Spell', color: '#d2d6ff', accent: '#ffffff', shape: 'star' },
  embervein_staff: { name: 'Embervein', color: '#a369ff', accent: '#ffac59', shape: 'rift' },
};
export const CAST = { duration: 2.8, release: .82, impact: 1.3, end: 1.85 };
export const FISHING = { duration: 10, drop: 1.6, land: 2.45, retrieve: 7.4, retrieved: 8.65, distance: 1.5 };
export function ease(value: number) { const x = T.MathUtils.clamp(value, 0, 1); return x * x * (3 - 2 * x); }

/** Deterministic timeline: seeking, pausing and looping never leave a stale line. */
export function fishingDrop(time: number) {
  if (time < FISHING.drop) return 0;
  if (time < FISHING.land) return ease((time - FISHING.drop) / (FISHING.land - FISHING.drop));
  if (time < FISHING.retrieve) return 1;
  return 1 - ease((time - FISHING.retrieve) / (FISHING.retrieved - FISHING.retrieve));
}
export function createFishingLine() {
  const rings = 41, sides = 5;
  const positions = new T.BufferAttribute(new Float32Array(rings * sides * 3), 3).setUsage(T.DynamicDrawUsage);
  const geometry = new T.BufferGeometry(); geometry.setAttribute('position', positions);
  const indices: number[] = [];
  for (let i = 0; i < rings - 1; i++) for (let j = 0; j < sides; j++) {
    const a = i * sides + j, b = i * sides + (j + 1) % sides;
    indices.push(a, b, a + sides, b, b + sides, a + sides);
  }
  geometry.setIndex(indices);
  const material = new T.MeshBasicMaterial({ color: '#c0d0d7', side: T.DoubleSide });
  const object = new T.Mesh(geometry, material); object.name = 'Fishing free line'; object.frustumCulled = false;
  const end = new T.Vector3(), start = new T.Vector3(), target = new T.Vector3(), p = new T.Vector3();
  const tangent = new T.Vector3(), cross = new T.Vector3(), up = new T.Vector3(0, 0, 1), normal = new T.Vector3();
  return { object,
    update(tip: T.Vector3, origin: T.Vector3, forward: T.Vector3, time: number, active: boolean) {
      const drop = active ? fishingDrop(time) : 0;
      start.copy(tip); end.copy(tip); end.z = Math.max(.025, tip.z - .17);
      target.copy(origin).addScaledVector(forward, FISHING.distance); target.z = .025;
      // Smooth payout with a modest hanging curve; no overhead or long-distance cast.
      end.lerp(target, drop); tangent.copy(end).sub(start).normalize();
      cross.crossVectors(tangent, up); if (cross.lengthSq() < .001) cross.set(1, 0, 0); cross.normalize(); normal.crossVectors(tangent, cross).normalize();
      for (let i = 0; i < rings; i++) {
        const u = i / (rings - 1); p.copy(start).lerp(end, u);
        p.z = Math.max(.018, p.z - Math.sin(Math.PI * u) * (.025 + .09 * drop));
        for (let j = 0; j < sides; j++) {
          const a = j * Math.PI * 2 / sides;
          positions.setXYZ(i * sides + j, p.x + .0017 * (cross.x * Math.cos(a) + normal.x * Math.sin(a)), p.y + .0017 * (cross.y * Math.cos(a) + normal.y * Math.sin(a)), p.z + .0017 * (cross.z * Math.cos(a) + normal.z * Math.sin(a)));
        }
      }
      positions.needsUpdate = true;
    },
    dispose() { geometry.dispose(); material.dispose(); },
  };
}

/** One bounded effect: charge, directed release, trailing particles, then a fading impact. */
export function createSpellEffect(style: typeof SPELL_STYLES[string]) {
  const object = new T.Group(); object.name = style.name;
  const coreMaterial = new T.MeshBasicMaterial({ color: style.accent, transparent: true, blending: T.AdditiveBlending, depthWrite: false, toneMapped: false });
  const coreGeometry = new T.IcosahedronGeometry(1, 1);
  const core = new T.InstancedMesh(coreGeometry, coreMaterial, 8); core.frustumCulled = false; object.add(core);
  const count = 96, positions = new T.BufferAttribute(new Float32Array(count * 3), 3).setUsage(T.DynamicDrawUsage);
  const seeds = Float32Array.from({ length: count }, (_, i) => i / count);
  const geometry = new T.BufferGeometry(); geometry.setAttribute('position', positions); geometry.setAttribute('seed', new T.BufferAttribute(seeds, 1));
  const material = new T.ShaderMaterial({ transparent: true, blending: T.AdditiveBlending, depthWrite: false, toneMapped: false,
    uniforms: { color: { value: new T.Color(style.color) }, accent: { value: new T.Color(style.accent) }, opacity: { value: 1 }, pixels: { value: 400 } },
    vertexShader: `attribute float seed; uniform float pixels; varying float s; void main(){s=seed;vec4 p=modelViewMatrix*vec4(position,1.);gl_Position=projectionMatrix*p;gl_PointSize=clamp(pixels*(.013+.022*(1.-seed))/max(.1,-p.z),1.,32.);}`,
    fragmentShader: `uniform vec3 color,accent;uniform float opacity;varying float s;void main(){vec2 p=gl_PointCoord*2.-1.;float r=dot(p,p);float a=exp(-r*5.)*(1.-smoothstep(.7,1.,r));if(a<.008)discard;gl_FragColor=vec4(mix(color,accent,exp(-r*24.)),a*opacity*(1.-s*.55));
#include <colorspace_fragment>
}`,
  });
  const particles = new T.Points(geometry, material); particles.frustumCulled = false; object.add(particles);
  const arcPositions = new T.BufferAttribute(new Float32Array(4 * 20 * 2 * 3), 3).setUsage(T.DynamicDrawUsage);
  const arcGeometry = new T.BufferGeometry(); arcGeometry.setAttribute('position', arcPositions);
  const arcMaterial = new T.LineBasicMaterial({ color: style.color, transparent: true, blending: T.AdditiveBlending, depthWrite: false, toneMapped: false });
  const arcs = new T.LineSegments(arcGeometry, arcMaterial); arcs.frustumCulled = false; object.add(arcs);
  const ringGeometry = new T.RingGeometry(.91, 1, 40), ringMaterial = coreMaterial.clone();
  const ring = new T.Mesh(ringGeometry, ringMaterial); ring.material.side = T.DoubleSide; object.add(ring);
  const viewport = new T.Vector4(); particles.onBeforeRender = (renderer, _scene, camera) => { renderer.getCurrentViewport(viewport); material.uniforms.pixels.value = viewport.w * camera.projectionMatrix.elements[5] * .5; };
  const target = new T.Vector3(), center = new T.Vector3(), dir = new T.Vector3(), side = new T.Vector3(), lift = new T.Vector3();
  const p = new T.Vector3(), up = new T.Vector3(0, 0, 1), matrix = new T.Matrix4(), q = new T.Quaternion(), scale = new T.Vector3();
  const hash = (i: number) => { const x = Math.sin(i * 127.1 + 19.7) * 43758.5453; return x - Math.floor(x); };
  return { object,
    update(tip: T.Vector3, origin: T.Vector3, forward: T.Vector3, time: number, active: boolean) {
      object.visible = active && time >= .12 && time <= CAST.end;
      if (!object.visible) return;
      const charging = time < CAST.release, impact = time >= CAST.impact;
      const charge = ease((time - .12) / (CAST.release - .12)), travel = T.MathUtils.clamp((time - CAST.release) / (CAST.impact - CAST.release), 0, 1);
      const burst = ease((time - CAST.impact) / (CAST.end - CAST.impact)), fade = impact ? 1 - burst : charge;
      target.copy(origin).addScaledVector(forward, 2.5); target.z = origin.z + 1.05;
      center.copy(tip).lerp(target, travel); center.z += Math.sin(travel * Math.PI) * .10;
      dir.copy(target).sub(tip).normalize(); side.crossVectors(dir, up).normalize(); lift.crossVectors(side, dir).normalize();
      const size = charging ? .012 + .055 * charge : impact ? .06 * (1 - burst) : .06;
      core.count = style.shape === 'petals' ? 3 : style.shape === 'star' ? 6 : 1;
      q.setFromUnitVectors(up, dir);
      for (let i = 0; i < core.count; i++) {
        p.copy(center);
        if (core.count > 1) p.addScaledVector(side, Math.cos(i * Math.PI * 2 / core.count + time) * size * .8).addScaledVector(lift, Math.sin(i * Math.PI * 2 / core.count + time) * size * .8);
        scale.set(size * .65, size * .65, size * (style.shape === 'lance' ? 2.8 : style.shape === 'ember' ? 1.8 : 1));
        matrix.compose(p, q, scale); core.setMatrixAt(i, matrix);
      }
      core.instanceMatrix.needsUpdate = true; coreMaterial.opacity = fade;
      for (let i = 0; i < count; i++) {
        const f = i / count, angle = i * 2.39996 + time * (style.shape === 'helix' ? 8 : 4);
        if (impact) {
          const z = hash(i + 10) * 2 - 1, radius = (.10 + .40 * burst) * (.3 + .7 * hash(i + 50));
          p.copy(target).addScaledVector(side, Math.cos(angle) * Math.sqrt(1 - z * z) * radius).addScaledVector(lift, Math.sin(angle) * Math.sqrt(1 - z * z) * radius).addScaledVector(dir, z * radius * .4);
        } else if (charging) {
          const radius = (.035 + .16 * (1 - charge)) * (.4 + .6 * f);
          p.copy(tip).addScaledVector(side, Math.cos(angle) * radius).addScaledVector(lift, Math.sin(angle) * radius).addScaledVector(dir, (hash(i) - .5) * radius);
        } else {
          const trail = Math.max(0, travel - f * .24), r = .018 + .04 * f;
          p.copy(tip).lerp(target, trail); p.z += Math.sin(trail * Math.PI) * .10;
          p.addScaledVector(side, Math.cos(angle) * r).addScaledVector(lift, Math.sin(angle) * r);
        }
        positions.setXYZ(i, p.x, p.y, p.z);
      }
      positions.needsUpdate = true; material.uniforms.opacity.value = fade;
      for (let lane = 0; lane < 4; lane++) for (let segment = 0; segment < 20; segment++) for (let end = 0; end < 2; end++) {
        const f = (segment + end) / 20, angle = lane * Math.PI / 2 + f * Math.PI * (style.shape === 'helix' || style.shape === 'rift' ? 4 : 2) + time * 3;
        const radius = impact ? .10 + burst * .4 : .04 + .06 * charge;
        const jag = style.shape === 'bolt' ? (hash(segment + end + lane * 21 + Math.floor(time * 18)) - .5) * .09 : 0;
        p.copy(center).addScaledVector(side, Math.cos(angle) * (radius + jag)).addScaledVector(lift, Math.sin(angle) * (radius + jag));
        if (!charging && !impact) p.addScaledVector(dir, -(1 - f) * .3);
        arcPositions.setXYZ((lane * 20 + segment) * 2 + end, p.x, p.y, p.z);
      }
      arcPositions.needsUpdate = true; arcMaterial.opacity = fade * .7;
      ring.position.copy(center); ring.quaternion.copy(q); ring.scale.setScalar(impact ? .07 + .42 * burst : .04 + .11 * charge); ringMaterial.opacity = fade * .45;
    },
    dispose() { coreGeometry.dispose(); coreMaterial.dispose(); geometry.dispose(); material.dispose(); arcGeometry.dispose(); arcMaterial.dispose(); ringGeometry.dispose(); ringMaterial.dispose(); },
  };
}
