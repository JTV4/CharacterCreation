from pathlib import Path
p=Path('scripts/fit_alpha_pass_hats.py')
s=p.read_text().replace('import json','import json\nimport base64\nimport struct\nimport math')
pos=s.index('\ndef clear():')
s=s[:pos]+'''
def coverage(meshes, size=64):
    """Rasterize the hat's lowest surface in each vertical column, in glTF axes.
    Generated from geometry alone; every hairstyle uses the same coverage map.
    """
    points = [(v.co.x, -v.co.y, v.co.z) for o in meshes for v in o.data.vertices]
    x0, z0 = min(p[0] for p in points), min(p[1] for p in points)
    x1, z1 = max(p[0] for p in points), max(p[1] for p in points)
    heights = [65535] * (size * size)
    for obj in meshes:
        obj.data.calc_loop_triangles()
        for tri in obj.data.loop_triangles:
            pts = [obj.data.vertices[i].co for i in tri.vertices]
            a, b, c = [((p.x-x0)/(x1-x0)*size, (-p.y-z0)/(z1-z0)*size, p.z) for p in pts]
            denom = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(denom) < 1e-10:
                continue
            for z in range(max(0, math.floor(min(p[1] for p in (a,b,c)))), min(size, math.ceil(max(p[1] for p in (a,b,c))))):
                for x in range(max(0, math.floor(min(p[0] for p in (a,b,c)))), min(size, math.ceil(max(p[0] for p in (a,b,c))))):
                    u = ((b[1]-c[1])*(x+.5-c[0])+(c[0]-b[0])*(z+.5-c[1]))/denom
                    v = ((c[1]-a[1])*(x+.5-c[0])+(a[0]-c[0])*(z+.5-c[1]))/denom
                    w = 1-u-v
                    if min(u,v,w) >= -1e-7:
                        h = round((u*a[2]+v*b[2]+w*c[2])*1000)
                        heights[z*size+x] = min(heights[z*size+x], h)
    packed = struct.pack('<'+'H'*len(heights), *[0 if h==65535 else h for h in heights])
    return {'size':size, 'bounds':[x0,z0,x1-x0,z1-z0], 'heights':base64.b64encode(packed).decode()}
''' +s[pos:]
a=s.index('        band = crown')
b=s.index('        before =',a)
s=s[:a]+s[b:]
s=s.replace("        bpy.ops.object.select_all(action='DESELECT')", "        profiles[sex][name.lower()] = coverage(meshes)\n        bpy.ops.object.select_all(action='DESELECT')")
p.write_text(s)
