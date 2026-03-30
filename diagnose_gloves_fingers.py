"""
diagnose_gloves_fingers.py
Map the left hand finger geometry: Z cross-sections to find web spaces.
Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python diagnose_gloves_fingers.py
"""
import bpy, math

GLB = "viewer/public/equipment/shell_gloves.glb"
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=GLB)

m = next(o for o in bpy.data.objects if o.type == 'MESH' and len(o.vertex_groups) > 0)
verts = list(m.data.vertices)

# Left hand only (X > 0.45)
left = [v for v in verts if v.co.x > 0.45]

# Bin by Z to find finger rows
z_vals = [v.co.z for v in left]
z_min, z_max = min(z_vals), max(z_vals)
print(f"Left hand Z range: {z_min:.3f} .. {z_max:.3f}")

# Slice into Z bands of 5mm
band_size = 0.005
z_lo = z_min
bands = {}
while z_lo < z_max:
    z_hi = z_lo + band_size
    band_verts = [v for v in left if z_lo <= v.co.z < z_hi]
    if band_verts:
        ys = [v.co.y for v in band_verts]
        xs = [v.co.x for v in band_verts]
        bands[round(z_lo, 3)] = {
            "count": len(band_verts),
            "x_range": (round(min(xs),3), round(max(xs),3)),
            "y_range": (round(min(ys),3), round(max(ys),3)),
        }
    z_lo = round(z_lo + band_size, 4)

print("\nZ-band cross-sections (left hand):")
for z, info in sorted(bands.items()):
    print(f"  Z={z:.3f}: {info['count']:3d} verts  X={info['x_range']}  Y={info['y_range']}")

# Find the web space between pinky and ring: look at finger clusters in X
# Fingers should cluster at distinct Z positions for the extended fingertips
# Look at high-X region (X > 0.70) to find finger clusters
print("\nFinger tips (X > 0.70):")
tips = [v for v in left if v.co.x > 0.70]
if tips:
    # Cluster by Z
    z_coords = sorted(set(round(v.co.z, 2) for v in tips))
    print(f"  Distinct Z positions: {z_coords}")
    for z in z_coords:
        cluster = [v for v in tips if abs(v.co.z - z) < 0.008]
        if cluster:
            xs = [v.co.x for v in cluster]
            ys = [v.co.y for v in cluster]
            print(f"  Z≈{z:.3f}: {len(cluster)} verts  X={round(min(xs),3)}..{round(max(xs),3)}  Y={round(min(ys),3)}..{round(max(ys),3)}")

# Find web spaces: concave areas between fingers in Z
# Web space = local minimum in vertex density between finger clusters
print("\nAll unique Z values in left hand (rounded to 3dp):")
all_z = sorted(set(round(v.co.z, 3) for v in left))
print(f"  {all_z}")

# Distinct Y clusters at the finger base (X 0.58-0.75, represents knuckle zone)
print("\nKnuckle zone (X 0.58-0.75) Y distribution:")
knuckle = [v for v in left if 0.58 < v.co.x < 0.75]
if knuckle:
    ys = sorted(v.co.y for v in knuckle)
    print(f"  Y range: {round(min(ys),3)} .. {round(max(ys),3)}")
    # Show Y histogram
    y_min, y_max = min(ys), max(ys)
    n_bins = 10
    bin_w = (y_max - y_min) / n_bins
    for i in range(n_bins):
        lo = y_min + i*bin_w
        hi = lo + bin_w
        cnt = sum(1 for y in ys if lo <= y < hi)
        print(f"    Y {lo:.3f}..{hi:.3f}: {'#'*cnt} ({cnt})")
