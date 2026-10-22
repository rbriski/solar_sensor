#!/usr/bin/env python3
"""Export a 2 mm rigid tracing ring using the enclosure's exact gasket profile."""
import json
import math
import cadquery as cq
import trimesh
from build_enclosure import ROOT, gasket


def main():
    height = 2.0
    shape = gasket(z=0, height=height).val()
    assert shape.isValid() and len(shape.Solids()) == 1
    # Independently check the rounded-rectangle area and asymmetric opening.
    area = lambda w, h, r: w*h - (4-math.pi)*r*r
    expected = (area(152, 58, 7)-area(137.4, 51.4, 5.7))*height
    assert abs(shape.Volume()-expected) < 1e-5
    section = shape.Faces()
    top = next(f for f in section if abs(f.Center().z-height) < 1e-6)
    assert len(top.innerWires()) == 1
    hole = top.innerWires()[0].BoundingBox()
    assert abs(hole.xlen-137.4) < 1e-6 and abs(hole.ylen-51.4) < 1e-6
    assert abs((hole.xmin+hole.xmax)/2-4) < 1e-6
    out = ROOT/'models'
    for ext in ('stl', 'step'):
        cq.exporters.export(shape, str(out/f'gasket-tracer.{ext}'), tolerance=0.01, angularTolerance=0.05)
    mesh = trimesh.load(out/'gasket-tracer.stl', force='mesh')
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert all(abs(a-b) < .02 for a,b in zip(mesh.extents, (152,58,height)))
    result = dict(valid_solid=True, watertight=True, dimensions_mm=[152,58,height],
                  opening_mm=[137.4,51.4], opening_offset_x_mm=4,
                  exact_enclosure_gasket_profile=True, volume_mm3=shape.Volume(),
                  usage='Rigid tracing tool only; install the cut foam gasket, not this PETG ring.')
    (out/'gasket-tracer-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
