"""
bake_equipment_transform.py
===========================
Bake an `equipTransform` captured in the viewer's "Mesh Inspector" into a
piece of equipment GLB permanently, so the file can be shipped to a different
project without needing the viewer's runtime offset.

Math (matches `exportSlotAsGlb` in viewer/src/components/EquipmentMeshRenderer.tsx):

    v_yup_baked = Cinv · M_zup · C · v_yup_original
    n_yup_baked = normalize( (M_yup_effective^-T)[:3,:3] · n_yup_original )

where:

    C        = Rx(+90°) · S(1.9 / 1.75)        # _yupToZupCorrection
    Cinv     = C^-1
    M_zup    = T(position) · R_xyz(rotation_deg) · S(scale)
    rotation is Three.js default Euler order 'XYZ' (in degrees):
        R_xyz = Rx(rx) · Ry(ry) · Rz(rz)

Only the mesh's POSITION + NORMAL attributes (and the POSITION accessor
min/max) are modified.  The skeleton, bone inverse-bind matrices, node
transforms, materials and textures are left completely untouched — so the
file remains structurally identical to the source weighted GLB and will rig
correctly against the same Mixamo skeleton in any downstream project.

Usage:
    python3.13 bake_equipment_transform.py

Edit the INPUT / OUTPUT / TRANSFORM constants below.
"""

import math
import struct
from typing import Tuple

import numpy as np
import pygltflib


INPUT_GLB  = "viewer/public/equipment/Female/Hats/GreenRangedHatWeighted.glb"
OUTPUT_GLB = "viewer/public/equipment/Female/Hats/GreenRangedHatPositioned.glb"

# Values captured via the viewer's "Copy" button on the Mesh Inspector.
POSITION  = (0.2300, 0.2100, -0.8700)
ROTATION  = (4.0000, -5.0000, 180.0000)   # degrees, Three.js Euler 'XYZ'
SCALE     = 1.4000

CHARACTER_HEIGHT_SCALE = 1.9 / 1.75


def rx(angle_rad: float) -> np.ndarray:
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array([
        [1, 0,  0, 0],
        [0, c, -s, 0],
        [0, s,  c, 0],
        [0, 0,  0, 1],
    ], dtype=np.float64)


def ry(angle_rad: float) -> np.ndarray:
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array([
        [ c, 0, s, 0],
        [ 0, 1, 0, 0],
        [-s, 0, c, 0],
        [ 0, 0, 0, 1],
    ], dtype=np.float64)


def rz(angle_rad: float) -> np.ndarray:
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    return np.array([
        [c, -s, 0, 0],
        [s,  c, 0, 0],
        [0,  0, 1, 0],
        [0,  0, 0, 1],
    ], dtype=np.float64)


def translation(t: Tuple[float, float, float]) -> np.ndarray:
    m = np.eye(4, dtype=np.float64)
    m[:3, 3] = t
    return m


def uniform_scale(s: float) -> np.ndarray:
    m = np.eye(4, dtype=np.float64)
    m[0, 0] = m[1, 1] = m[2, 2] = s
    return m


def compose_mzup(position, rotation_deg, scale) -> np.ndarray:
    # Three.js Quaternion.setFromEuler('XYZ') is equivalent to q = qx * qy * qz
    # so the rotation matrix is R = Rx · Ry · Rz (column vectors).
    rx_m = rx(math.radians(rotation_deg[0]))
    ry_m = ry(math.radians(rotation_deg[1]))
    rz_m = rz(math.radians(rotation_deg[2]))
    R = rx_m @ ry_m @ rz_m
    return translation(position) @ R @ uniform_scale(scale)


def compose_c() -> np.ndarray:
    return rx(math.pi / 2) @ uniform_scale(CHARACTER_HEIGHT_SCALE)


def transform_positions(positions: np.ndarray, M: np.ndarray) -> np.ndarray:
    # positions: (N, 3), homogeneous transform, drop w.
    N = positions.shape[0]
    h = np.hstack([positions.astype(np.float64), np.ones((N, 1))])
    out = (M @ h.T).T
    return out[:, :3].astype(np.float32)


def transform_normals(normals: np.ndarray, M: np.ndarray) -> np.ndarray:
    # Normals use inverse-transpose of upper-3x3, then renormalize.
    upper = M[:3, :3]
    N_inv_T = np.linalg.inv(upper).T
    out = (N_inv_T @ normals.astype(np.float64).T).T
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    norms = np.where(norms > 1e-12, norms, 1.0)
    out = out / norms
    return out.astype(np.float32)


def read_accessor_f32x3(gltf: pygltflib.GLTF2, accessor_idx: int, blob: bytes) -> Tuple[np.ndarray, int, int]:
    """Return (array (N,3) float32, absolute_offset, byte_stride)."""
    acc = gltf.accessors[accessor_idx]
    assert acc.componentType == pygltflib.FLOAT, "expected FLOAT"
    assert acc.type == "VEC3", "expected VEC3"
    bv = gltf.bufferViews[acc.bufferView]
    stride = bv.byteStride if bv.byteStride else 12
    abs_off = (bv.byteOffset or 0) + (acc.byteOffset or 0)
    n = acc.count
    if stride == 12:
        arr = np.frombuffer(blob, dtype=np.float32, count=n * 3, offset=abs_off).reshape(n, 3).copy()
    else:
        arr = np.empty((n, 3), dtype=np.float32)
        for i in range(n):
            arr[i] = np.frombuffer(blob, dtype=np.float32, count=3, offset=abs_off + i * stride)
    return arr, abs_off, stride


def write_accessor_f32x3(blob: bytearray, arr: np.ndarray, abs_off: int, stride: int) -> None:
    n = arr.shape[0]
    if stride == 12:
        packed = arr.astype(np.float32).tobytes()
        blob[abs_off:abs_off + len(packed)] = packed
    else:
        for i in range(n):
            struct.pack_into("<3f", blob, abs_off + i * stride,
                             float(arr[i, 0]), float(arr[i, 1]), float(arr[i, 2]))


def main() -> None:
    gltf = pygltflib.GLTF2().load(INPUT_GLB)
    blob = bytearray(gltf.binary_blob())

    C     = compose_c()
    Cinv  = np.linalg.inv(C)
    M_zup = compose_mzup(POSITION, ROTATION, SCALE)
    M     = Cinv @ M_zup @ C

    print("M_zup =")
    print(M_zup)
    print("C =")
    print(C)
    print("M_yup_effective =")
    print(M)

    # Process every primitive (this GLB has a single hat primitive).
    total_verts = 0
    for mi, mesh in enumerate(gltf.meshes):
        for pi, prim in enumerate(mesh.primitives):
            pos_idx = prim.attributes.POSITION
            nrm_idx = prim.attributes.NORMAL

            positions, p_off, p_stride = read_accessor_f32x3(gltf, pos_idx, bytes(blob))
            new_positions = transform_positions(positions, M)
            write_accessor_f32x3(blob, new_positions, p_off, p_stride)

            pacc = gltf.accessors[pos_idx]
            pacc.min = [float(v) for v in new_positions.min(axis=0)]
            pacc.max = [float(v) for v in new_positions.max(axis=0)]
            print(f"mesh[{mi}] prim[{pi}]: POSITION {positions.shape[0]} verts")
            print(f"  old bounds: min={positions.min(axis=0)} max={positions.max(axis=0)}")
            print(f"  new bounds: min={new_positions.min(axis=0)} max={new_positions.max(axis=0)}")

            if nrm_idx is not None:
                normals, n_off, n_stride = read_accessor_f32x3(gltf, nrm_idx, bytes(blob))
                new_normals = transform_normals(normals, M)
                write_accessor_f32x3(blob, new_normals, n_off, n_stride)
                print(f"  NORMAL  {normals.shape[0]} verts transformed (inverse-transpose + renormalize)")

            total_verts += positions.shape[0]

    gltf.set_binary_blob(bytes(blob))
    gltf.save(OUTPUT_GLB)
    print(f"\nWrote {OUTPUT_GLB}  ({total_verts} verts baked)")


if __name__ == "__main__":
    main()
