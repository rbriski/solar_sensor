"""Render physically separate top jumpers / underside local links, revision 5."""
from pathlib import Path
import html
import json

ROOT = Path(__file__).parent
PINS = dict(zip(['B2','C2','D2','E2','F2','G2','H2','B8','C8','D8','E8','F8','G8','H8'],
                ['D0 / A0','D1','D2','D3','D4','D5','D6','5V unused','GND','3V3','D10','D9','D8','D7']))
PARTS = [('R3 · 4.7 kΩ','L2','L6'),('R1 · 100 kΩ','P3','T3'),
         ('R2 · 100 kΩ','P5','T5'),('C1 · 100 nF','P7','R7'),('J1 · removable','V3','V4')]
# @column,row are bend positions, never extra solder joints.
JUMPERS = [
 ('W1','A0','#7653a5',['B1','@0.6,2','@0.6,15','O3']),
 ('W2','DATA','#b17a00',['D1','@1.4,4','@1.4,11','K2']),
 ('W3','3V3','#c63f3f',['D9','J9','K6']),
 ('W4','TB1 DATA','#b17a00',['L1','M2','U2','U7']),
 ('W5','TB1 3V3','#c63f3f',['L7','M8','U8']),
]
BARE = [
 ('G0',['C8','C10','T10']),
 ('G1',['L9','L10']),('G2',['R7','R10']),('G3',['T5','T10']),
 ('S1',['B1','B2']),('S2',['D1','D2']),('S3',['D8','D9']),
 ('S5',['K2','L2','L1']),('S6',['K6','L6','L7']),
 ('S9',['O3','P3']),('S10',['P3','P7']),
 ('S12',['V4','T4','T3']),('S14',['V3','X3']),
 ('S15',['U7','W7']),('S16',['U8','W8']),
 ('G4',['T10','W10','W9']),
]
TERMINAL = ['W7','W8','W9']
EXTERNAL = [('TB1 YELLOW / DATA','W7','#b17a00'),('TB1 RED / 3V3','W8','#c63f3f'),
            ('TB1 BLACK / GND','W9','#334155'),('BAT+ sense lead','X3','#d35a20')]
def grid(p):
    if p.startswith('@'): return tuple(map(float,p[1:].split(',')))
    return int(p[1:]),ord(p[0])-64

def render(bottom=False):
    def xy(p):
        c,r=grid(p);x=80+(c-1)*36
        return (484-x if bottom else x),85+(r-1)*28
    def text(x,y,s,attr=''):
        return f'<text x="{x}" y="{y}" {attr}>{html.escape(s)}</text>'
    def path(points):
        return ' '.join(('M' if i==0 else 'L')+f'{xy(p)[0]},{xy(p)[1]}' for i,p in enumerate(points))
    def dot(p,color='#334155',radius=5):
        x,y=xy(p)
        return f'<circle cx="{x}" cy="{y}" r="{radius}" fill="white" stroke="{color}" stroke-width="2"/>'
    s=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 790 810" role="img">',
       '<title>'+('Bottom: shared ground rail and local bare links, mirrored' if bottom else 'Top: insulated point-to-point jumpers only')+'</title>',
       '<rect width="790" height="810" fill="white"/>',
       '<style>text{font:13px sans-serif;fill:#203646}.small{font-size:11px}.heading{font-size:18px;font-weight:bold}</style>',
       text(30,25,'BOTTOM · ground rail + local bare links' if bottom else 'TOP · insulated point-to-point jumpers','class="heading"'),
       text(30,47,'Flip left-to-right; keep USB at top. Column 10 is the shared ground rail.' if bottom else 'Solid colored lines are insulated wires on TOP. Strip only the two ends.'),
       '<rect x="57" y="62" width="370" height="694" rx="8" fill="#f5edcf" stroke="#95825f"/>']
    for c in range(1,11):
        x,y=xy('A'+str(c));s.append(text(x,76,str(c),'text-anchor="middle"'))
    for r in range(1,25):
        letter=chr(64+r);s.append(text(43,85+(r-1)*28+4,letter,'text-anchor="end"'))
        for c in range(1,11):
            x,y=xy(letter+str(c));s.append(f'<circle cx="{x}" cy="{y}" r="5" fill="#e2bd70" stroke="#9b814b"/><circle cx="{x}" cy="{y}" r="1.8" fill="white"/>')
    x1,y=xy('B2');x2,_=xy('B8');left=min(x1,x2)
    s.append(f'<rect x="{left-13}" y="{y-24}" width="242" height="213" rx="8" fill="{ "none" if bottom else "#d5e8e1"}" stroke="#78988d" stroke-dasharray="{5 if bottom else 0}"/>')
    s.append(f'<rect x="{left+83}" y="{y-37}" width="54" height="25" fill="#bbc9ce" stroke="#647580"/>')
    s.append(text(left+110,y+70,'XIAO C6','text-anchor="middle" class="heading"'))
    s.append(text(left+110,y+90,'B2–H2 / B8–H8','text-anchor="middle"'))
    # Part bodies exist only on top; underside shows their solder pads.
    for name,a,b in PARTS:
        if not bottom:
            xa,ya=xy(a);xb,yb=xy(b)
            s.append(f'<path d="M{xa},{ya} L{xb},{yb}" stroke="#596b71" stroke-width="2"/>')
            if name.startswith('R'):
                if ya==yb:s.append(f'<rect x="{min(xa,xb)+25}" y="{ya-8}" width="{abs(xb-xa)-50}" height="16" fill="#f8ddae" stroke="#80603a"/>')
                else:s.append(f'<rect x="{xa-8}" y="{ya+25}" width="16" height="{yb-ya-50}" fill="#f8ddae" stroke="#80603a"/>')
            elif name.startswith('C1'):
                s.append(f'<ellipse cx="{xa}" cy="{(ya+yb)/2}" rx="12" ry="15" fill="#e4b075" stroke="#936638"/>')
            else:s.append(f'<rect x="{min(xa,xb)-7}" y="{ya-9}" width="{abs(xa-xb)+14}" height="18" fill="#3d5263"/>')
        s.extend([dot(a),dot(b)])
    # TB1 outline is approximate: dry-fit the purchased body before soldering.
    if not bottom:
        tx,ty=xy('W7');tx2,_=xy('W9')
        s.append(f'<rect x="{min(tx,tx2)-15}" y="{ty-15}" width="{abs(tx2-tx)+30}" height="48" rx="4" fill="#b6d6ba" stroke="#356e42" stroke-width="2"/>')
        s.append(text(min(tx,tx2)+36,ty+26,'TB1 ↓','text-anchor="middle" class="small"'))
    if bottom:
        for name,points in BARE:
            color = '#334155' if name.startswith('G') else '#6e5738'
            s.append(f'<path data-link="{name}" d="{path(points)}" fill="none" stroke="{color}" stroke-width="4" stroke-linejoin="round"/>')
    else:
        for name,net,color,points in JUMPERS:
            s.append(f'<path d="{path(points)}" fill="none" stroke="white" stroke-width="7" stroke-linejoin="round"/>')
            s.append(f'<path data-wire="{name}" d="{path(points)}" fill="none" stroke="{color}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>')
    for name,net,color,points in JUMPERS:
        for p in [points[0],points[-1]]:s.append(dot(p,color,6))
    for p,label in PINS.items():
        x,y=xy(p);side=1 if x<240 else -1;s.append(dot(p,'#437569'))
        s.append(text(x+side*12,y+4,label,'class="small" text-anchor="'+('start' if side==1 else 'end')+'"'))
    for label,p,color in EXTERNAL:
        x,y=xy(p);s.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{color}" stroke="white" stroke-width="2"/>')
    items=[]
    if bottom:
        items=[('GROUND RAIL + BARE LINKS','')]+[(name,' ↔ '.join(pts)) for name,pts in BARE]
    else:
        items=[('INSULATED TOP WIRES','')]+[(f'{n} · {net}',f'{pts[0]} ↔ {pts[-1]}') for n,net,color,pts in JUMPERS]
        items+=[('TB1 · openings toward X','W7 / W8 / W9'),('COMPONENT PLACEMENT','')]+[(n,f'{a} ↔ {b}') for n,a,b in PARTS]
    items += [('EXTERNAL LEADS','')]+[(label,p) for label,p,color in EXTERNAL]
    yy=92
    for label,detail in items:
        if bottom:
            s.append(text(450,yy,label+('  '+detail if detail else ''),'class="small"'));yy+=26
        else:
            s.append(text(450,yy,label,'font-weight="bold"'))
            if detail:s.append(text(450,yy+16,detail,'class="small"'));yy+=30
            else:yy+=23
    s.append(text(60,780,'Each jumper has its own two free holes. Rings mark wire ends; no intermediate joints.','class="small"'))
    s.append(text(60,799,'10 × 24 isolated pads · 2.54 mm pitch · USB faces row A; optional sense jumper J1 stays open','class="small"'))
    s.append('</svg>');return ''.join(s)

if __name__ == '__main__':
    for bottom,name in [(False,'component-side.svg'),(True,'solder-side.svg')]:
        (ROOT/name).write_text(render(bottom))
    (ROOT/'layout.json').write_text(json.dumps(dict(revision=5,coordinate_system='Rows A-X, columns 1-10',
        pins=PINS,parts=PARTS,top_jumpers=JUMPERS,bottom_bare_links=BARE,external=EXTERNAL,terminal=TERMINAL),indent=2))
