#!/usr/bin/env python3
"""Water-temperature pipe enclosure R1. Millimetres; print poses exported.

X follows the pipe and both cables. Z=0 is the case floor underside.
The DS16 mounting screws are transferred from the purchased part: its public
drawing dimensions the base diameter, NOT the screw pitch circle.
"""
from pathlib import Path
import json
import cadquery as cq
import trimesh

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'models'
P = dict(revision='R1', body_length=154, body_width=60, body_height=46,
         floor=3, ordinary_wall=2.4, power_wall=13, lid_thickness=3,
         foam_uncompressed=1.6, foam_closed_gap=1.2,
         board_size=[70,30], board_centers=[66,26], board_bottom_z=9,
         populated_height=30, board_x_min=-17, usb_projection=25,
         usb_flex_bay=22, pipe_od=69.85, liner_thickness=1,
         pipe_center_z=-44.925, saddle_radius=35.925,
         saddle_centers_x=[-42,42], saddle_width_x=28,
         tie_channel=[9,3.5], ds16_outer_diameter=39, ds16_height=19,
         ds16_entry_hole=16.2, cable_center_z=23, pg7_hole=13.2)
BOARD = [(x,y) for x in (-15,51) for y in (-13,13)]
LID = [(x,y) for x in (-62,62) for y in (-32,32)]
SADDLE_LOCAL = [(-9,-23),(9,23)]
MOUNT = [(x+dx,y) for x in P['saddle_centers_x'] for dx,y in SADDLE_LOCAL]


def box(x,y,z,dx,dy,dz):
    return cq.Workplane('XY').box(dx,dy,dz,centered=False).translate((x,y,z))


def cyl(x,y,z,d,h):
    return cq.Workplane('XY').center(x,y).circle(d/2).extrude(h).translate((0,0,z))


def axial(x,y,z,d,length):
    return cq.Workplane().add(cq.Solid.makeCylinder(d/2,length,cq.Vector(x,y,z),cq.Vector(1,0,0)))


def wire(w,h,r,z=0,cx=0):
    f=cq.Face.makeFromWires(cq.Workplane('XY').rect(w,h).val())
    return f.fillet2D(r,f.Vertices()).outerWire().translate((cx,0,z))


def rr(w,h,r,z,height,cx=0):
    return cq.Workplane('XY').add(wire(w,h,r,z,cx)).toPending().extrude(height)


def body():
    s=rr(154,60,8,0,46)
    s=s.cut(rr(138.6,55.2,5.6,3,35,cx=5.3))
    transition=cq.Solid.makeLoft([wire(138.6,55.2,5.6,38,5.3),wire(136,50,5,42,4)])
    s=s.cut(transition).cut(rr(136,50,5,42,6,cx=4))
    # A full-height 13 mm end wall accepts transfer-drilled DS16 screw pilots.
    s=s.cut(axial(-78,0,23,16.2,15)).cut(axial(73,0,23,13.2,5))
    for x,y in LID:
        s=s.union(cyl(x,y,0,12,46)).cut(cyl(x,y,37,2.6,10))
    for x,y in BOARD:
        s=s.union(cyl(x,y,3,4,6)).cut(cyl(x,y,3.7,1.3,5.4))
    for x,y in MOUNT:
        # Blind from BELOW: the screw cannot open a path into the enclosure.
        s=s.union(cyl(x,y,3,9,6)).cut(cyl(x,y,-0.1,2.6,7.6))
    return s.clean()


def lid():
    # Outside face on bed. Flip over X to assemble, retaining X cable direction.
    s=rr(154,60,8,0,3)
    for x,y in LID:
        s=s.union(cyl(x,y,0,12,3)).union(cyl(x,y,3,5,1.2))
        s=s.cut(cyl(x,y,-0.1,3.4,4.5))
    lip=rr(135.2,49.2,4.6,3,3,cx=4).cut(rr(132,46,3,2.9,3.2,cx=4))
    return s.union(lip).clean()


def saddle():
    s=box(-14,-30,-18,28,60,18)
    s=s.cut(axial(-15,0,P['pipe_center_z'],2*P['saddle_radius'],30))
    s=s.cut(box(-4.5,-31,-5.5,9,62,3.5))
    for x,y in SADDLE_LOCAL:
        s=s.cut(cyl(x,y,-19,3.4,20)).cut(cyl(x,y,-19,7,10))
    return s.clean()


def saddle_print(s):
    return s.rotate((0,0,0),(0,1,0),90).translate((18,30,14))


def gasket(z=46,height=1.2):
    return rr(152,58,7,z,height).cut(rr(137.4,51.4,5.7,z-.1,height+.2,cx=4))


def overlap(a,b):
    return a.val().intersect(b.val()).Volume()


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    b,l,seat=body(),lid(),saddle()
    prints={'body':b,'lid':l,'saddle':saddle_print(seat)}
    assembled={'body':b,'lid':l.rotate((0,0,0),(1,0,0),180).translate((0,0,50.2))}
    assembled.update({f'saddle_{i+1}':seat.translate((x,0,0)) for i,x in enumerate(P['saddle_centers_x'])})
    pcb=box(-17,-15,9,70,30,1.5)
    for x,y in BOARD:pcb=pcb.cut(cyl(x,y,8.9,2,1.7))
    refs={'perfboard':pcb,'populated_board_clearance':box(-17,-15,10.5,70,30,28.5),
          'usb_plug_allowance':box(-42,-10,10.5,25,20,28.5),
          'pipe':axial(-100,0,P['pipe_center_z'],P['pipe_od'],200),
          'ds16_shell':axial(-96,0,23,39,19),
          'pg7_locknut_allowance':axial(67,0,23,24,7.6),
          'gasket_compressed':gasket()}
    checks={'revision':'R1','parts':{},'clearances':{},'fasteners':{},
            'limits':['No physical fit, seal, thermal or long-term tie/fastener testing claimed.',
                      'DS16 base fastener positions must be transfer-drilled from the purchased part.',
                      'PG7 locknut is a conservative 24 mm diameter, 7.6 mm deep envelope.',
                      'USB plug cross-section is an allowance, not measured; confirm 16 mm connector passage.',
                      'Black PETG brand/temperature label not supplied; generic profile is a starting point.']}
    for name,s in prints.items():
        assert s.val().isValid() and len(s.solids().vals())==1,name
        cq.exporters.export(s,str(OUT/f'{name}.step'))
        cq.exporters.export(s,str(OUT/f'{name}.stl'),tolerance=.025,angularTolerance=.08)
        m=trimesh.load_mesh(OUT/f'{name}.stl')
        assert m.is_watertight and m.is_winding_consistent and m.volume>0,name
        assert abs(m.bounds[0,2])<1e-5,(name,m.bounds)
        checks['parts'][name]=dict(count=2 if name=='saddle' else 1,
             dimensions_mm=m.extents.round(4).tolist(),volume_mm3=round(m.volume,2),
             triangles=len(m.faces),valid_single_solid=True,watertight=True)
    pairs=list(assembled.items())
    for i,(an,a) in enumerate(pairs):
        for bn,bp in pairs[i+1:]:assert overlap(a,bp)<.01,(an,bn,overlap(a,bp))
    for rn,r in refs.items():
        for pn,p in assembled.items():assert overlap(r,p)<.01,(rn,pn,overlap(r,p))
    # Fit actual tie gauges and screw head/shaft envelopes in both saddles.
    for x in P['saddle_centers_x']:
        gauge=box(x-3.8,-31,-5.2,7.6,62,2)
        for pn,p in assembled.items():assert overlap(gauge,p)<.01,('tie',pn)
    for x,y in MOUNT:
        head=cyl(x,y,-12.5,6,3.5)
        shaft=cyl(x,y,-9.5,3,16)
        for n,p in assembled.items():
            assert overlap(head,p)<.01,('saddle screw head',n)
            if n!='body':assert overlap(shaft,p)<.01,('saddle screw shaft',n)
        assert overlap(head,refs['pipe'])<.01,'screw head contacts pipe'
    checks['clearances']=dict(printed_pairwise_intersections_mm3='<0.01',
          hardware_vs_printed_intersections_mm3='<0.01',board_to_lid_mm=8.2,
          usb_projection_mm=25,usb_flex_bay_mm=22,lid_lip_side_clearance_mm=.4,
          pipe_liner_radial_mm=1,tie_gauge_passed_mm=[7.6,2],
          mounting_pilot_sealed_roof_mm=1.5,pg7_wall_mm=2.4,
          ds16_wall_mm=13,board_mount_centers_mm=[66,26])
    for key,length,stack,depth,pilot,count in [
        ('perfboard',6,1.5,5.3,1.3,4),('lid',12,4.7,9,2.6,4),
        ('saddles',16,9.5,7.5,2.6,4)]:
        clearance=depth-(length-stack)
        assert clearance>0
        checks['fasteners'][key]=dict(count=count,length_mm=length,stack_mm=stack,
              pilot_diameter_mm=pilot,pilot_depth_mm=depth,tip_clearance_mm=round(clearance,2))
    checks['gasket']=dict(material='1/16 inch (about 1.6 mm) closed-cell foam, one continuous ring',
                         closed_gap_mm=1.2,nominal_compression_percent=25)
    assembly=cq.Assembly(name='water_temperature_R1')
    for name,s in assembled.items():assembly.add(s,name=name,color=cq.Color(.12,.12,.13))
    for name,s in refs.items():
        colour=(.65,.65,.65) if name in ('pipe','ds16_shell') else (.15,.5,.35)
        assembly.add(s,name=name+'_REFERENCE',color=cq.Color(*colour))
        cq.exporters.export(s,str(OUT/f'{name}-reference.stl'),tolerance=.05,angularTolerance=.10)
    assembly.save(str(OUT/'assembly-reference.step'))
    # Non-print assembled saddle mesh makes render transforms unambiguous.
    cq.exporters.export(seat,str(OUT/'saddle-assembled-reference.stl'),tolerance=.025,angularTolerance=.08)
    (OUT/'parameters.json').write_text(json.dumps(P,indent=2)+'\n')
    (OUT/'validation.json').write_text(json.dumps(checks,indent=2)+'\n')
    print(json.dumps(checks,indent=2))


if __name__=='__main__':main()
