#!/usr/bin/env python3
"""Current fitted solar sensor enclosure. All dimensions are millimetres.

Run with CadQuery 2.8 and trimesh installed. Outputs printable meshes, STEP files,
an assembled reference model, and measured validation results. Hardware shapes
are envelopes for clearance checking, not printable replicas.
"""
from pathlib import Path
import argparse
import json
import math
import cadquery as cq
import trimesh

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "models"

P = dict(revision="body4-tray5-arm6", outer_x=164.0, outer_y=152.0, base_height=42.0,
         wall=2.4, floor=3.0, corner_radius=14.0, lid_thickness=4.0,
         gland_hole=13.2, gland_centres_y=[38.0, 78.0], gland_centre_z=16.0,
         ring_id=158.42, ring_section=2.62, ring_size="AS568-164",
         groove_x=144.0, groove_y=132.0, groove_radius=22.0,
         groove_width=3.8, groove_depth=2.0, panel_air_gap=25.0,
         perfboard_thickness_assumed=1.5, tray_thickness=2.4)
LID_SCREWS = [(10,10),(154,10),(10,142),(154,142),(5,76),(159,76)]
TRAY_SCREWS = [(26,25),(138,25),(26,127),(138,127)]
DFR_SCREWS = [(64,25),(119,25),(64,50),(119,50)]
# Measured 70 x 30 board, approx. 2 mm mounting holes with 1 mm material
# from board edge to hole edge. Verify your board before printing.
# Centres are therefore 2 mm inset, giving a 66 x 26 mm pattern.
PERF_CORNER_SCREWS = [(62,64),(128,64),(128,90),(62,90)]
PANEL_SCREWS = [(10,50),(154,50),(10,102),(154,102)]


def rr_wire(w,h,r,z=0,cx=82,cy=76):
    # Fillet a face rather than a solid so the same exact section can be lofted.
    face = cq.Face.makeFromWires(cq.Workplane("XY").rect(w,h).val())
    return face.fillet2D(r, face.Vertices()).outerWire().translate((cx,cy,z))


def rr(w,h,r,z,height,cx=82,cy=76):
    return cq.Workplane("XY").add(rr_wire(w,h,r,z,cx,cy)).toPending().extrude(height)


def box(x,y,z,dx,dy,dz):
    return cq.Workplane("XY").box(dx,dy,dz,centered=False).translate((x,y,z))


def cyl(x,y,z,d,h):
    return cq.Workplane("XY").center(x,y).circle(d/2).extrude(h).translate((0,0,z))


def hex_nut(x,y,z,h=2.8,af=5.8):
    return cq.Workplane("XY").center(x,y).polygon(6,2*af/math.sqrt(3)).extrude(h).translate((0,0,z))


def cut_holes(shape,pts,d,z,h):
    for x,y in pts:
        shape=shape.cut(cyl(x,y,z,d,h))
    return shape


def base():
    s=rr(164,152,14,0,42)
    s=s.cut(rr(159.2,147.2,11.6,3,25))
    taper=cq.Solid.makeLoft([rr_wire(159.2,147.2,11.6,28),rr_wire(136,124,18,40)])
    s=s.cut(taper).cut(rr(136,124,18,40,4))
    groove=rr(147.8,135.8,23.9,40,3).cut(rr(140.2,128.2,20.1,39.9,3.2))
    s=s.cut(groove)
    for x,y in LID_SCREWS:
        s=s.cut(cyl(x,y,29,3.4,14)).cut(hex_nut(x,y,35.2))
        # Side-loading nuts remain entirely outside the closed gasket loop.
        start,width=(-1,x+1) if x<82 else (x,165-x)
        s=s.cut(box(start,y-2.9,35.2,width,5.8,2.8))
    for y in P["gland_centres_y"]:
        hole=cq.Solid.makeCylinder(6.6,8,cq.Vector(158,y,16),cq.Vector(1,0,0))
        s=s.cut(hole)
    for x,y in TRAY_SCREWS:
        s=s.union(cyl(x,y,3,8,3)).cut(cyl(x,y,2,2.6,5))
    # External mounting ears only; roof attachment remains a separate design.
    for x in (50,114):
        for y in (-4,156):
            ear=rr(20,16,3,0,5,cx=x,cy=y)
            s=s.union(ear).cut(cyl(x,y-2 if y<0 else y+2,-1,4.5,7))
    ear=rr(30,20,3,0,5,cx=176,cy=118)
    s=s.union(ear)
    for x in (171,183):
        s=s.cut(cyl(x,118,-1,3.4,7)).cut(hex_nut(x,118,-0.1,2.9))
    return s.clean()


def lid_print():
    # Outside face is on the bed; the smooth sealing face prints upward.
    s=rr(164,152,14,0,4)
    lip=rr(135.2,123.2,17.6,4,3).cut(rr(132.4,120.4,16.2,3.9,3.2))
    return cut_holes(s.union(lip),LID_SCREWS,3.4,-1,10).clean()


def tray_print():
    # Local z=0 is the underside. Assembly raises the complete tray by 6 mm.
    s=rr(134,122,17,0,2.4)
    s=cut_holes(s,TRAY_SCREWS,3.4,-1,5)
    for x,y in DFR_SCREWS:
        s=s.union(cyl(x,y,2.4,6,10)).cut(cyl(x,y,7.4,2.6,6))
    for x,y in PERF_CORNER_SCREWS:
        # M1.7 x 6 self-tapping screw through 1.5 mm PCB; 5.3 mm blind pilot.
        s=s.union(cyl(x,y,2.4,5.5,1.3)).union(cyl(x,y,2.4,4,6))
        s=s.cut(cyl(x,y,3.1,1.3,5.4))
    # Broad smooth supports, with under-cell room for a soft hook-and-loop strap.
    for x in (80,121):
        s=s.union(rr(8,28,2,2.4,1.6,cx=x,cy=115.5))
    # Open corner fences allow leads and avoid squeezing the pouch.
    for x in (74.25,131.75):
        for y in (101.75,129.25):
            s=s.union(rr(1.5,10.5,0.7,2.4,3,cx=x,cy=y))
    for y in (97.25,133.75):
        for x in (80.25,125.75):
            s=s.union(rr(10.5,1.5,0.7,2.4,3,cx=x,cy=y))
    for y in (95.0,134.0):
        s=s.cut(box(94.5,y,-1,11,2,5))
    return s.clean()


def panel_frame():
    s=rr(164,162,3,0,6)
    s=s.cut(rr(128,148,0.5,-1,8))
    s=s.cut(rr(130.8,150.8,0.4,3,4))
    s=cut_holes(s,LID_SCREWS[:4],3.4,-1,8)
    for x,y in PANEL_SCREWS:
        s=s.cut(cyl(x,y,-1,3.4,8)).cut(hex_nut(x,y,-0.1,2.9))
    for x in (45,119):
        # Drain the panel pocket at its downhill edge.
        s=s.cut(box(x-1.5,-6,3,3,9,4))
    return s.clean()


def panel_clip():
    s=rr(12,10,1,0,3,cx=2,cy=0)
    slot=cq.Workplane("XY").slot2D(5,3.4,0).extrude(5).translate((0,0,-1))
    return s.cut(slot)


def spacer():
    return cyl(0,0,0,10,25).cut(cyl(0,0,-1,3.4,27))


def probe_arm():
    s=rr(160,16,4,0,4,cx=80,cy=8)
    widening=cq.Workplane("XY").polyline([(88,0),(100,-2),(156,-2),(156,18),(100,18),(88,16)]).close().extrude(4)
    s=s.union(widening).union(rr(12,20,4,0,4,cx=154,cy=8))
    s=cut_holes(s,[(7,8),(19,8)],3.4,-1,6)
    for x in (110,125,140):
        for y in (2,14):
            slot=cq.Workplane("XY").center(x,y).slot2D(8,3.2,0).extrude(6).translate((0,0,-1))
            s=s.cut(slot)
    return s.clean()


def volume_intersection(a,b):
    return a.val().intersect(b.val()).Volume()


def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUT)
    args=parser.parse_args()
    OUT=args.output
    OUT.mkdir(parents=True,exist_ok=True)
    pieces={"base":base(), "lid":lid_print(), "tray":tray_print(),
            "panel_frame":panel_frame(), "panel_spacer":spacer(),
            "panel_clip":panel_clip(),
            "probe_arm":probe_arm()}
    counts={"base":1,"lid":1,"tray":1,"panel_frame":1,"panel_spacer":4,
            "panel_clip":4,"probe_arm":1}
    checks={"revision":"body4-tray5-arm6","parts":{},"clearances":{},"assumptions":[
        "Perfboard thickness modeled 1.5 mm; hole centers 66 x 26 mm. Builder confirmed fit; measure substitute boards.",
        "Panel clips overlap 1 mm of its edge; check the inactive border before tightening.",
        "PG7 nut clearance uses a conservative 24 mm diameter envelope, not a measured nut.",
        "Digital checks do not establish weatherproofing, roof anchorage, or thermal safety."]}
    for name,part in pieces.items():
        assert part.val().isValid(),name
        assert len(part.solids().vals())==1,(name,len(part.solids().vals()))
        cq.exporters.export(part,str(OUT/f"{name}.step"))
        cq.exporters.export(part,str(OUT/f"{name}.stl"),tolerance=0.03,angularTolerance=0.10)
        mesh=trimesh.load_mesh(OUT/f"{name}.stl")
        assert mesh.is_watertight and mesh.is_winding_consistent and mesh.volume>0,name
        checks["parts"][name]={"count":counts[name],"valid_solid":True,"watertight_mesh":True,
            "dimensions_mm":[round(v,3) for v in mesh.extents],"volume_mm3":round(mesh.volume,1),
            "triangles":len(mesh.faces)}
    assembled={"base":pieces["base"],"lid":pieces["lid"].rotate((0,76,0),(1,76,0),180).translate((0,0,46)),
               "tray":pieces["tray"].translate((0,0,6)),"panel_frame":pieces["panel_frame"].translate((0,0,71)),
               "probe_arm":pieces["probe_arm"].translate((164,110,5))}
    for i,(x,y) in enumerate(LID_SCREWS[:4]):
        assembled[f"panel_spacer_{i+1}"]=pieces["panel_spacer"].translate((x,y,46))
    for i,(x,y) in enumerate(PANEL_SCREWS):
        clip=pieces["panel_clip"]
        if x>82: clip=clip.rotate((0,0,0),(0,0,1),180)
        assembled[f"panel_clip_{i+1}"]=clip.translate((x,y,77))
    perfboard=cut_holes(box(60,62,14.4,70,30,1.5),PERF_CORNER_SCREWS,2.0,14.3,1.7)
    dfr=cut_holes(box(60,21,18.4,63,33,1.6),DFR_SCREWS,3.0,18.3,1.8)
    refs={"solar_panel_REFERENCE":box(17,1,74,130,150,2.5),
          "battery_REFERENCE":box(76,99,10,54,33,10),
          "DFR0559_PCB_REFERENCE":dfr,
          "DFR0559_COMPONENTS_REFERENCE":box(63,24,20,57,27,9),
          "perfboard_PCB_REFERENCE":perfboard,
          "perfboard_COMPONENTS_REFERENCE":box(60,62,15.9,70,30,10)}
    # Check all printed solids against one another. Intentional contacts have zero volume.
    for i,(an,a) in enumerate(assembled.items()):
        for bn,b in list(assembled.items())[i+1:]:
            overlap=volume_intersection(a,b)
            assert overlap<0.01,(an,bn,"printed part collision",overlap)
    checks["clearances"]["printed_part_collision_check"]="passed; pairwise intersection < 0.01 mm3"
    for rn,r in refs.items():
        for pn,p in assembled.items():
            overlap=volume_intersection(r,p)
            assert overlap<0.01,(rn,pn,"hardware collision",overlap)
    checks["clearances"]["hardware_envelopes_vs_printed_parts"]="passed; no volume intersections"
    for y in P["gland_centres_y"]:
        envelope=cq.Workplane().add(cq.Solid.makeCylinder(12,7.6,cq.Vector(154,y,16),cq.Vector(1,0,0)))
        for name in ("base","tray","lid"):
            overlap=volume_intersection(envelope,assembled[name])
            assert overlap<0.01,("gland locknut envelope",name,overlap)
    checks["clearances"]["gland_locknut_24mm_envelopes"]="passed; floor/rim/tray clear"
    checks["clearances"]["usb_service_bay_mm"]=45
    checks["clearances"]["tray_to_throat_per_side_mm"]=1.0
    checks["clearances"]["lid_locator_to_throat_per_side_mm"]=0.4
    perim=2*(144+132-4*22)+2*math.pi*22
    stretch=perim/(math.pi*(P["ring_id"]+P["ring_section"]))-1
    checks["gasket"]={"part":"AS568-164, EPDM 70, e.g. Global O-Ring E70164",
        "id_mm":158.42,"section_mm":2.62,"groove_centreline_perimeter_mm":round(perim,3),
        "neutral_axis_stretch_percent":round(100*stretch,2),
        "nominal_squeeze_percent":round(100*(1-2/2.62),2),
        "nominal_gland_fill_percent":round(100*math.pi*(2.62/2)**2/(3.8*2),2),
        "groove_width_mm":3.8,"groove_depth_mm":2,"qualification":"nominal geometry only; manufactured dimensions and seal test still required"}
    # Direct-to-plastic screw length = material stack + tip penetration.
    # Penetration includes a self-tapper's tapered point; no washers assumed.
    checks["board_fasteners"]={
        "perfboard":{"screw":"M1.7 x 6 self-tapping", "stack_mm":1.5, "pilot_diameter_mm":1.3, "pilot_depth_mm":5.3},
        "dfrobot":{"screw":"M3 x 5 self-tapping", "stack_mm":1.6, "pilot_diameter_mm":2.6, "pilot_depth_mm":5.0},
        "tray":{"screw":"M3 x 6 self-tapping", "stack_mm":2.4, "pilot_diameter_mm":2.6, "pilot_depth_mm":4.0}}
    for spec,length in zip(checks["board_fasteners"].values(),(6,5,6)):
        spec["penetration_including_point_mm"]=round(length-spec["stack_mm"],2)
        spec["tip_clearance_mm"]=round(spec["pilot_depth_mm"]-spec["penetration_including_point_mm"],2)
        assert spec["tip_clearance_mm"]>0
    checks["board_fasteners_note"]="Diameters recalled by original builder; lengths derived from modeled board/tray thickness. Tray clearance is only 0.4 mm; verify actual screw length and print. Match thread family to pilot."
    assembly=cq.Assembly(name="solar_sensor_enclosure")
    for n,p in assembled.items():
        assembly.add(p,name=n,color=cq.Color(0.76,0.79,0.82) if n in ("base","lid") else cq.Color(0.21,0.37,0.45))
    for n,p in refs.items():
        rgb=(0.05,0.12,0.22) if "solar" in n else ((0.75,0.75,0.78) if "battery" in n else (0.10,0.43,0.27))
        assembly.add(p,name=n,color=cq.Color(*rgb))
    assembly.save(str(OUT/"assembly-reference.step"))
    (OUT/"validation.json").write_text(json.dumps(checks,indent=2)+"\n")
    (OUT/"parameters.json").write_text(json.dumps(P,indent=2)+"\n")
    print(json.dumps(checks,indent=2))


if __name__=="__main__":
    main()
