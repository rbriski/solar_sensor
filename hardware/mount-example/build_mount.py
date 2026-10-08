#!/usr/bin/env python3
"""Optional site-specific clamp mount with self-tapping saddles. All dimensions in mm.

Measured collector dimensions are approximate. Geometry checks establish modeled
clearances, not installed fit, roof anchorage or a wind rating.
"""
from pathlib import Path
import argparse
import sys
import json
import math
import cadquery as cq
import trimesh
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"enclosure"))
import build_enclosure as old

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "models"
PITCH = 304.8
R = PITCH / 2
MOUNT = [(-32,-82),(32,-82),(-32,82),(32,82)]
SADDLE_BOLTS = [(-15,-23),(15,23)]


def rr(w,h,r,z,t,cx=0,cy=0):
    return old.rr(w,h,r,z,t,cx,cy)


def holes(s, points, z, height, d=4.5):
    return old.cut_holes(s,points,d,z,height)


def nut_pockets(s, points, z):
    for x,y in points:
        s=s.cut(old.hex_nut(x,y,z,5.7,7.6))
    return s


def tube(x0,length,zc=0,radius=12.7):
    return cq.Workplane().add(cq.Solid.makeCylinder(radius,length,cq.Vector(x0,0,zc),cq.Vector(1,0,0)))


def frame():
    s=rr(190,190,10,0,8).cut(rr(152,130,8,-1,10))
    for x in (-77.5,77.5):
        s=s.union(rr(35,40,3,0,8,x,0))
    root=[]
    for a in (0,90,180,270):
        for r in (70,88):
            root.append((r*math.cos(math.radians(a)),r*math.sin(math.radians(a))))
    s=holes(s,MOUNT+root,-1,10)
    return nut_pockets(s,MOUNT,-.1).clean()


def arm():
    # Local X is radial; the two slots translate the complete saddle assembly.
    pts=[(58,-18),(104,-18),(126,-33),(195,-33),(195,33),(126,33),(104,18),(58,18)]
    s=cq.Workplane("XY").polyline(pts).close().extrude(12)
    s=s.edges("|Z").fillet(3)
    s=holes(s,[(70,0),(88,0)],-1,14)
    s=nut_pockets(s,[(70,0),(88,0)],-.1)
    for dx,y in SADDLE_BOLTS:
        # Extra lateral clearance allows alignment with slightly warped spokes.
        # Use 12 mm OD M4 washers over these 6 mm-wide slots.
        slot=cq.Workplane("XY").center(R+dx,y).slot2D(30,6,0).extrude(14).translate((0,0,-1))
        s=s.cut(slot)
    return s.clean()


def saddle():
    s = rr(44, 64, 4, 0, 22).edges('|X and >Z').fillet(3)
    s = s.cut(tube(-23, 46, radius=14))
    s = s.cut(old.box(-7, -34, 20.8, 14, 68, 3))
    for x, y in SADDLE_BOLTS:
        s = s.cut(old.cyl(x, y, 22-20.0, 3.5, 20.0+1))
        # Small entry chamfer centers the screw without wedging the top surface.
        lead = cq.Solid.makeCone(1.75, 2.25, .5, cq.Vector(x, y, 21.5))
        s = s.cut(lead)
    return s.clean()


def spacer():
    return old.cyl(0,0,0,12,20).cut(old.cyl(0,0,-1,4.5,22)).clean()


def export(s,name):
    assert s.val().isValid() and len(s.solids().vals())==1,name
    cq.exporters.export(s,str(OUT/f"{name}.step"))
    cq.exporters.export(s,str(OUT/f"{name}.stl"),tolerance=.025,angularTolerance=.08)
    mesh=trimesh.load_mesh(OUT/f"{name}.stl")
    assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0,name
    return dict(extents_mm=list(mesh.extents),volume_mm3=float(mesh.volume),watertight=True)


def overlap(a,b):
    return a.val().intersect(b.val()).Volume()


def band_path_estimate():
    """Conservative 2D convex hull of unrounded cap and lined tube."""
    r=13.7
    pts=sorted(set([(-32.,0.),(32.,0.),(-32.,22.),(32.,22.)]+[
        (r*math.cos(i*math.pi/180),r*math.sin(i*math.pi/180)) for i in range(360)]))
    cross=lambda a,b,c:(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def half(seq):
        result=[]
        for p in seq:
            while len(result)>1 and cross(result[-2],result[-1],p)<=0:result.pop()
            result.append(p)
        return result[:-1]
    h=half(pts)+half(reversed(pts))
    return sum(math.dist(a,b) for a,b in zip(h,h[1:]+h[:1]))


def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUT)
    args=parser.parse_args()
    OUT=args.output
    OUT.mkdir(parents=True,exist_ok=True)
    f,a,s,p=frame(),arm(),saddle(),spacer()
    # Print saddle on its axial end: every layer contains its complete arch.
    sp=s.rotate((0,0,0),(0,1,0),-90).translate((22,32,22))
    audit={name:export(shape,name) for name,shape in (
        ("carrier",f),("arm",a),("saddle",sp),("spacer-20",p))}
    export(s,"saddle-assembly-reference")
    assert 50.8 - 12 - 20 - 1 < 20  # Tip clears closed pilot floor.
    for x,y in SADDLE_BOLTS:
        assert overlap(s,old.cyl(x,y,2,3.49,21)) < 1e-6
        assert overlap(s,old.cyl(x,y,.1,3.4,1.8)) > 16

    assert overlap(s,tube(-40,80))<1e-6
    assert overlap(s,tube(-40,80,zc=-38.1))<1e-6
    # Band head manufacturer's envelope, positioned over saddle's crown.
    head=old.box(-6.5,-13,20.8,13,26,11)
    for dx,y in SADDLE_BOLTS:
        assert overlap(head,old.cyl(dx,y,-1,4.5,70))<1e-6
    # Nominal assembled Z: upper tube center=0; saddle top=22; spacers to42;
    # arms42..54; carrier54..62; existing enclosure begins at62.
    frame_z=54
    f_world=f.translate((0,0,frame_z))
    body=cq.importers.importStep(str(ROOT.parent/"enclosure/models/base.step")).translate((-82,-76,62))
    assert overlap(f_world,body)<1e-6
    # Confirm new ear bores against the already-printed body solid.
    for x,y in MOUNT:
        assert overlap(body,old.cyl(x,y,61,4.4,7))<1e-6
    assembly=cq.Assembly(name="Clamp_mount_reference")
    assembly.add(f_world,name="carrier",color=cq.Color(.18,.43,.46))
    assembly.add(body,name="EXISTING_ENCLOSURE_REFERENCE",color=cq.Color(.82,.85,.85))
    assembled_parts=[]
    for i,angle in enumerate((0,90,180,270)):
        rot=lambda shape:shape.rotate((0,0,0),(0,0,1),angle)
        aw=rot(a.translate((0,0,42)))
        sw=rot(s.translate((R,0,0)))
        hw=rot(head.translate((R,0,0)))
        upper=rot(tube(R-48,96))
        lower=rot(tube(R-48,96,zc=-38.1))
        assert overlap(aw,body)<1e-6 and overlap(aw,f_world)<1e-6
        assert overlap(aw,hw)<1e-6 and overlap(sw,lower)<1e-6
        assert overlap(sw,upper)<1e-6
        for name,shape,col in (("arm",aw,(.18,.43,.46)),("saddle",sw,(.3,.54,.57)),
            ("UPPER_SUPPORT_REFERENCE",upper,(.24,.26,.27)),("LOWER_SUPPORT_REFERENCE",lower,(.24,.26,.27)),
            ("BAND_HEAD_REFERENCE",hw,(.67,.7,.72))):
            assembly.add(shape,name=f"{name}_{i}",color=cq.Color(*col))
        for j,(dx,y) in enumerate(SADDLE_BOLTS):
            pw=rot(p.translate((R+dx,y,22)))
            assert overlap(pw,hw)<1e-6 and overlap(pw,body)<1e-6
            assembly.add(pw,name=f"spacer_{i}_{j}",color=cq.Color(.3,.54,.57))
            # #8 x 2-inch self-tapping screw, 1 mm washer, 12 mm arm, 20 mm spacer.
            bolt=rot(old.cyl(R+dx,y,4.2,4.3,50.8))
            assert overlap(bolt,upper)<1e-6 and overlap(bolt,lower)<1e-6
        assembled_parts.extend([aw,sw])
    for i,x in enumerate(assembled_parts):
        for y in assembled_parts[i+1:]: assert overlap(x,y)<1e-6
    assembly.save(str(OUT/"mount-assembly-reference.step"))
    # Each printed saddle fits the nominal square opening in plan. Clamp head
    # is above the tube and the thin band alone enters the gap below it.
    assert 64<73.025 and 44<73.025
    assert 12.7-1-.65>11
    assert 42-(20.8+11)>10
    loop=band_path_estimate()
    assert 40<loop/math.pi<60
    audit=dict(revision="Current optional mount: self-tapping saddles",
        saddle_screw="#8 x 2 inch self-tapping, 50.8 mm",
        saddle_pilot=dict(diameter_mm=3.5,depth_mm=20,tip_clearance_mm=2.2),
        parts=audit,part_counts={"carrier":1,"arm":4,"saddle":4,"spacer-20":8},
        nominal_collector_mm=dict(opening=73.025,opposite_pitch=PITCH,tube_diameter=25.4,
                                  clear_gap_between_tubes=12.7,tube_center_pitch=38.1),
        attachment_centres_mm=MOUNT,radial_adjustment_mm=[R-12,R+12],
        opposite_pitch_adjustment_mm=[PITCH-24,PITCH+24],
        arm_saddle_slots_mm=[30,6],slot_washer_required="M4 large washer, 12 mm OD",
        saddle_envelope_mm=[44,64,22],saddle_groove_diameter_mm=28,
        saddle_bolts_mm=SADDLE_BOLTS,spacer_height_mm=20,
        band=dict(type="W4 stainless worm drive, 40–60 mm range, 9 mm band",
                  example="NORMA TORRO 40-60/9 C7 W4",band_thickness_mm=.65,
                  head_envelope_mm=[13,26,11],guide_channel_width_mm=14,
                  conservative_loop_perimeter_estimate_mm=round(loop,2),
                  equivalent_circular_diameter_mm=round(loop/math.pi,2),
                  estimate_note="Convex hull of unrounded saddle envelope and lined tube; physical routing remains a fit check",
                  source="https://www.normagroup.com/content/dam/normagroup-com/en/global/news/press-release-documents/2018/NORMA_TORRO_datasheet_en.pdf"),
        checks="Valid single solids; watertight meshes; existing enclosure ear clearance; no modeled tube, head, bolt, arm, spacer or enclosure interference",
        limits=["User dimensions are approximate; actual tube diameter, band routing and roof clearance must fit without forcing.",
                "1 mm EPDM liner intended; thin band loops under upper dry support only, not around both tubes.",
                "Manufacturer hose-clamp tightening torques are NOT a torque specification for these aged ABS supports.",
                "Hub wall tops and roof elevation were not modeled: position must retain clearance above hub and below bolt ends.",
                "No measured structural capacity, hot-weather creep life or wind rating established."])
    (OUT/"geometry-validation.json").write_text(json.dumps(audit,indent=2)+"\n")
    print(json.dumps(audit,indent=2))


if __name__=="__main__":main()
