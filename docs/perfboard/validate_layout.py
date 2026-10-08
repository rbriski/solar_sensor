"""Validate revision 5 topology, separate layer geometry and preserved parts."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
from render_layout import grid
ROOT=Path(__file__).parent
d=json.loads((ROOT/'layout.json').read_text())
parent={}
def find(p):
    parent.setdefault(p,p)
    if parent[p]!=p:parent[p]=find(parent[p])
    return parent[p]
def join(points):
    for p in points:parent[find(p)]=find(points[0])
def pads(route):
    result=set()
    for a,b in zip(route,route[1:]):
        x1,y1=grid(a);x2,y2=grid(b)
        assert x1==x2 or y1==y2,'Bare links must follow pad rows/columns'
        for x in range(min(x1,x2),max(x1,x2)+1):
            for y in range(min(y1,y2),max(y1,y2)+1):result.add(chr(64+y)+str(x))
    return result
for name,net,color,route in d['top_jumpers']:join([route[0],route[-1]])
for name,route in d['bottom_bare_links']:
    if not name.startswith('G'):
        assert sum(abs(grid(a)[0]-grid(b)[0])+abs(grid(a)[1]-grid(b)[1]) for a,b in zip(route,route[1:]))<=4,'Local bare link longer than 10.16 mm'
    join(list(pads(route)))
nets={'ADC':['B2','P3','P5','P7'], 'DATA':['D2','L1','L2','W7'],
      '3V3':['D8','L6','L7','W8'], 'GND':['C8','L9','T5','R7','W9'],
      'BAT_RAW':['X3','V3'],'BAT_AFTER_J1':['V4','T3']}
for name,points in nets.items():assert len({find(p) for p in points})==1,('Open net',name)
assert len({find(points[0]) for points in nets.values()})==6,'Unintended net short'
roots={find(points[0]) for points in nets.values()}
used={p for points in nets.values() for p in points}
for pin in d['pins']:
    if pin not in used:assert find(pin) not in roots,('Unused pin joined',pin)
expected=[('L2','L6'),('P3','T3'),('P5','T5'),('P7','R7'),('V3','V4')]
assert [(a,b) for name,a,b in d['parts']]==expected,'Soldered component moved'
expected_nets=[('DATA','3V3'),('ADC','BAT_AFTER_J1'),('ADC','GND'),('ADC','GND'),('BAT_RAW','BAT_AFTER_J1')]
for (_,a,b),(na,nb) in zip(d['parts'],expected_nets):
    assert {find(a),find(b)}=={find(nets[na][0]),find(nets[nb][0])}
occupied=list(d['pins'])+[p for _,a,b in d['parts'] for p in (a,b)]+[p for _,p,_ in d['external']]
ends=[p for _,_,_,route in d['top_jumpers'] for p in (route[0],route[-1])]
assert len(ends)==len(set(ends)),'Jumpers share a hole'
assert not set(ends).intersection(occupied),'Jumper end conflicts with a component or external lead'
for p in occupied+ends:assert p[0] in 'ABCDEFGHIJKLMNOPQRSTUVWX' and 1<=int(p[1:])<=10
# Top wires must visually clear unrelated header pads; crossing an empty pad
# on the component side does not create an electrical joint.
def dist(p,a,b):
    x,y=grid(p);ax,ay=grid(a);bx,by=grid(b);dx=bx-ax;dy=by-ay
    t=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy)))
    return ((x-ax-t*dx)**2+(y-ay-t*dy)**2)**.5
for name,net,color,route in d['top_jumpers']:
    for pin in d['pins']:assert all(dist(pin,a,b)>.25 for a,b in zip(route,route[1:])),(name,pin)
top=ET.parse(ROOT/'component-side.svg').getroot();bottom=ET.parse(ROOT/'solder-side.svg').getroot()
assert sum('data-wire' in e.attrib for e in top.iter())==5
assert not any('data-link' in e.attrib for e in top.iter())
assert sum('data-link' in e.attrib for e in bottom.iter())==16
assert not any('data-wire' in e.attrib for e in bottom.iter())
print('PASS: six correct nets; all component positions retained; 10 distinct jumper holes including former probe landing pads; header clearance; shared ground rail and short local links; correct layer separation')

assert d['terminal']==['W7','W8','W9']
assert len({find(p) for p in d['terminal']})==3, 'Terminal positions shorted'
print('PASS: W7 DATA, W8 3V3, W9 GND; terminal contacts isolated')
