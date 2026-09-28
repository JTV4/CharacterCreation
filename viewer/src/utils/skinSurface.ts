import * as THREE from 'three';

const prepared = new WeakMap<THREE.BufferGeometry, THREE.BufferGeometry>();
const VERSION = 1;
const bell = (value: number, center: number, radius: number) => Math.exp(-0.5 * ((value - center) / radius) ** 2);

/** Rework-only, pigment-relative skin detail. No baked light, added triangles, or per-frame work. */
export function prepareSkinSurface(mesh: THREE.Mesh): void {
  if (!/^Base(?:Male|Female)Rework/i.test(mesh.name)) return;
  const source = mesh.geometry;
  if (source.userData.skinSurfaceVersion === VERSION) return;
  const existing = prepared.get(source);
  if (existing) { mesh.geometry = existing.clone(); return; }
  const positions = source.getAttribute('position');
  const normals = source.getAttribute('normal');
  const colors = source.getAttribute('color');
  if (!positions || !normals || !colors) return;
  const geometry = source.clone();
  const smooth = geometry.getAttribute('normal') as THREE.BufferAttribute;
  const pigment = geometry.getAttribute('color') as THREE.BufferAttribute;
  const buckets = new Map<string, number[]>();
  // Imported reworks have split vertices at face/UV boundaries. Average compatible
  // surface normals across those splits, without welding or changing skin weights.
  for (let i = 0; i < positions.count; i++) {
    if (Math.max(colors.getX(i), colors.getY(i), colors.getZ(i)) < .08) continue;
    const key = [positions.getX(i), positions.getY(i), positions.getZ(i)].map(v => Math.round(v * 100000)).join(',');
    const bucket = buckets.get(key);
    if (bucket) bucket.push(i); else buckets.set(key, [i]);
  }
  const normal = new THREE.Vector3(), other = new THREE.Vector3(), sum = new THREE.Vector3();
  for (const bucket of buckets.values()) for (const i of bucket) {
    normal.fromBufferAttribute(normals, i); sum.set(0, 0, 0);
    for (const j of bucket) {
      other.fromBufferAttribute(normals, j);
      // Keep sharp rims and opposing surfaces intact (mouth/eyelids/nostrils).
      if (normal.dot(other) > .35) sum.add(other);
    }
    if (sum.lengthSq() > 0) normal.lerp(sum.normalize(), .94).normalize();
    smooth.setXYZ(i, normal.x, normal.y, normal.z);
  }
  // Both authored bodies use X across, Y forward, -Z up in mesh-local space.
  // Normalize height so the same anatomical fields fit both rework proportions.
  let height = 0;
  for (let i = 0; i < positions.count; i++) height = Math.max(height, -positions.getZ(i));
  const female = /Female/i.test(mesh.name);
  const lipHeight = female ? .883 : .881;
  for (let i = 0; i < positions.count; i++) {
    const r = colors.getX(i), g = colors.getY(i), b = colors.getZ(i);
    if (Math.max(r, g, b) < .08) continue; // Preserve authored underwear and dark details.
    const x = positions.getX(i), y = positions.getY(i), h = -positions.getZ(i) / height;
    const front = THREE.MathUtils.smoothstep(y, .025, .07);
    const cheeks = bell(Math.abs(x), .052, .026) * bell(h, .909, .015) * front;
    const nose = bell(x, 0, .017) * bell(h, .902, .012) * front;
    const ears = bell(Math.abs(x), .095, .020) * bell(h, .918, .023);
    const lips = bell(x, 0, .026) * bell(h, lipHeight, .0033) * front;
    const warmth = Math.min(1, cheeks * .65 + nose * .5 + ears * .55);
    // Broad, low-contrast pigment variation rather than random triangle noise.
    const variation = .012 * Math.sin(x * 39 + y * 22) * Math.sin(h * 47 + x * 17);
    const base = .995 + variation;
    pigment.setXYZ(i,
      r * (base - .13 * lips),
      g * (base - .20 * warmth - .35 * lips),
      b * (base - .24 * warmth - .32 * lips));
  }
  smooth.needsUpdate = true; pigment.needsUpdate = true;
  geometry.userData.skinSurfaceVersion = VERSION;
  prepared.set(source, geometry);
  // Each character owns its geometry; equipment coverage can safely change indices.
  mesh.geometry = geometry.clone();
}
