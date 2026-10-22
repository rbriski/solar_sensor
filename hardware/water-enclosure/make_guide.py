#!/usr/bin/env python3
"""Generate the printable gasket template and static Gas City build guide."""
from pathlib import Path
import json
import math
from zipfile import ZipFile,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parent


def gasket_template():
    svg='''<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">
<rect width="210" height="297" fill="white"/>
<g font-family="sans-serif" fill="#172b29"><text x="20" y="20" font-size="6">Water-temperature R1 — lid gasket</text>
<text x="20" y="29" font-size="3.8">Print at 100% / Actual size. Check the 50 mm line.</text>
<text x="20" y="36" font-size="3.8">1/16 in (about 1.6 mm) closed-cell foam; one continuous ring.</text></g>
<g fill="none" stroke="black" stroke-width="0.25">
<rect x="29" y="51" width="152" height="58" rx="7"/>
<rect x="40.3" y="54.3" width="137.4" height="51.4" rx="5.7"/>
<path d="M30 135 H80 M30 132 V138 M80 132 V138"/></g>
<g font-family="sans-serif" font-size="4" fill="#172b29"><text x="54" y="83">Remove the center; keep the surrounding ring.</text>
<text x="20" y="122">Wide end (left) faces the grey DS16 USB gland.</text>
<text x="40" y="145">50 mm check line</text>
<text x="20" y="158">Outer: 152 × 58 mm, corner radius 7 mm.</text>
<text x="20" y="167">Opening: 137.4 × 51.4 mm, radius 5.7 mm.</text>
<text x="20" y="176">Opening is offset 4 mm toward the PG7 sensor end.</text>
<text x="20" y="190">Cut on a separate mat. Keep adhesive out of the cavity.</text></g></svg>'''
    (ROOT/'gasket-template.svg').write_text(svg)
    # Small vector PDF, in physical mm, with no extra rendering dependency.
    scale=72/25.4;commands=[]
    def text(x,y,size,s):
        s=s.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
        commands.append(f'BT /F1 {size} Tf 1 0 0 1 {x*scale:.4f} {(297-y)*scale:.4f} Tm ({s}) Tj ET')
    def rounded(x,y,w,h,r):
        # PDF uses a bottom-left origin; cubic approximation of circular corners.
        x*=scale;y=(297-y-h)*scale;w*=scale;h*=scale;r*=scale;k=.5522847498*r
        commands.append(f'{x+r} {y} m {x+w-r} {y} l {x+w-r+k} {y} {x+w} {y+r-k} {x+w} {y+r} c '
          f'{x+w} {y+h-r} l {x+w} {y+h-r+k} {x+w-r+k} {y+h} {x+w-r} {y+h} c '
          f'{x+r} {y+h} l {x+r-k} {y+h} {x} {y+h-r+k} {x} {y+h-r} c '
          f'{x} {y+r} l {x} {y+r-k} {x+r-k} {y} {x+r} {y} c h S')
    commands.append('0.7 w 0 G')
    text(20,20,17,'Water-temperature R1 - lid gasket')
    text(20,29,10,'Print at 100% / Actual size. Verify the 50 mm line.')
    text(20,36,10,'1/16 in (about 1.6 mm) closed-cell foam. Cut one continuous ring.')
    rounded(29,51,152,58,7);rounded(40.3,54.3,137.4,51.4,5.7)
    text(54,83,10,'Remove the center; keep the surrounding ring.')
    text(20,122,11,'Wide end (left) faces the grey DS16 USB gland.')
    for x1,y1,x2,y2 in [(30,135,80,135),(30,132,30,138),(80,132,80,138)]:
        commands.append(f'{x1*scale} {(297-y1)*scale} m {x2*scale} {(297-y2)*scale} l S')
    text(40,145,11,'50 mm check line')
    text(20,158,11,'Outer: 152 x 58 mm, corner radius 7 mm.')
    text(20,167,11,'Opening: 137.4 x 51.4 mm, corner radius 5.7 mm.')
    text(20,176,11,'Opening is offset 4 mm toward the PG7 sensor end.')
    text(20,190,11,'Cut on a separate mat. Keep adhesive out of the cavity.')
    stream='\n'.join(commands).encode('ascii')
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
       f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {210*scale} {297*scale}] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>'.encode(),
       b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
       f'<< /Length {len(stream)} >>\nstream\n'.encode()+stream+b'\nendstream']
    data=bytearray(b'%PDF-1.4\n');offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(data));data.extend(f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n')
    start=len(data);data.extend(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode())
    for off in offsets[1:]:data.extend(f'{off:010d} 00000 n \n'.encode())
    data.extend(f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
    (ROOT/'gasket-template.pdf').write_bytes(data)


def layout():
    (ROOT/'layout.svg').write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1040 540" role="img" aria-labelledby="title desc">
<title id="title">Water-temperature R1 top-view layout</title><desc id="desc">USB and probe cables leave opposite short ends along the pipe. Zip ties cross below the case at two saddle positions. The USB plug extends 25 millimetres beyond the 70 by 30 millimetre board, with 22 millimetres of flexible cable space before the inner wall.</desc>
<rect width="1040" height="540" fill="#f1f5f3"/>
<g font-family="sans-serif" fill="#213c34"><text x="40" y="42" font-size="25" font-weight="700">Cables follow the pipe. Ties cross underneath.</text>
<text x="40" y="72" font-size="16">Top view with lid removed · dimensions in mm · purchased glands shown as envelopes</text></g>
<g stroke="#203a34" stroke-width="2" fill="none"><path d="M150 120 V99 H766 V120 M150 110 H766"/></g>
<text x="458" y="102" text-anchor="middle" font-family="sans-serif" font-size="16">154</text>
<rect x="150" y="135" width="616" height="240" rx="32" fill="#30383c"/>
<rect x="202" y="145" width="554.4" height="220.8" rx="22.4" fill="#e3eae5"/>
<g fill="#f4ebd4" stroke="#ae8440" stroke-width="2"><rect x="390" y="195" width="280" height="120"/>
<circle cx="398" cy="203" r="4"/><circle cx="662" cy="203" r="4"/><circle cx="398" cy="307" r="4"/><circle cx="662" cy="307" r="4"/></g>
<rect x="290" y="225" width="100" height="60" rx="8" fill="#6c777c"/>
<path d="M202 255 H290 M670 255 H756" stroke="#be822b" stroke-width="7" fill="none"/>
<rect x="74" y="177" width="76" height="156" rx="12" fill="#aeb8b9" stroke="#5c6b70" stroke-width="2"/>
<rect x="766" y="213" width="72" height="84" rx="9" fill="#9babb0" stroke="#5c6b70" stroke-width="2"/>
<path d="M25 255 H74 M838 255 H960" stroke="#343d40" stroke-width="8"/>
<g stroke="#d09336" stroke-width="4" stroke-dasharray="8 6"><path d="M290 128 V390 M626 128 V390"/></g>
<g font-family="sans-serif" fill="#203a34" font-size="16" text-anchor="middle">
<text x="530" y="243" font-size="22" font-weight="700">70 × 30 perfboard</text><text x="530" y="273">66 × 26 screw centers</text>
<text x="342" y="211">25 mm plug</text><text x="247" y="300">22 mm</text><text x="247" y="320">cable space</text>
<text x="104" y="355">Grey DS16-P</text><text x="805" y="321">PG7</text>
<text x="95" y="410">USB power</text><text x="892" y="410">Probe cable</text>
<text x="458" y="438">Orange dashed lines: tie locations beneath the case, 84 mm apart</text></g>
<g font-family="sans-serif" fill="#4d625c" font-size="16"><text x="40" y="484">30 mm populated board height + 8.2 mm lid clearance · 69.85 mm pipe + 1 mm rubber liner</text>
<text x="40" y="512">Case including screw ears: 154 × 76 × 50.2 mm · saddle channels: 9 × 3.5 mm</text></g></svg>''')


def main():
    gasket_template();layout()
    audit=json.loads((ROOT/'bambu/project-validation.json').read_text())
    assert audit.get('reopened_and_resliced')
    with ZipFile(ROOT/'water-temperature-R1-CAD.zip','w',ZIP_DEFLATED) as z:
        for n in ('body','lid','saddle','gasket-tracer'):
            for ext in ('stl','step'):z.write(ROOT/'models'/f'{n}.{ext}',f'models/{n}.{ext}')
        for n in ('assembly-reference.step','parameters.json','validation.json','gasket-tracer-validation.json'):z.write(ROOT/'models'/n,'models/'+n)
        for n in ('build_enclosure.py','build_gasket_tracer.py','prepare_project.py','render.py','package_project.py','make_guide.py','README.md','gasket-template.pdf','gasket-template.svg','layout.svg'):
            z.write(ROOT/n,n)
    html='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Water Temperature · Pipe Enclosure R1</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f1f5f3;color:#213c34;font:17px/1.6 system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:28px 24px 70px}nav{display:flex;gap:24px;flex-wrap:wrap}a{color:#116959}h1{font-size:clamp(32px,5vw,52px);line-height:1.12;margin:24px 0 12px}h2{margin-top:32px}p{max-width:900px}.eyebrow{letter-spacing:.12em;text-transform:uppercase;font-size:13px;font-weight:700;color:#64746e}.chips,.downloads{display:flex;gap:12px;flex-wrap:wrap}.chips span{background:#dfeae3;border-radius:24px;padding:5px 13px;font-size:14px}.downloads a{background:#176757;color:white;padding:12px 18px;border-radius:8px;text-decoration:none;font-weight:650}.downloads a.secondary{background:#fff;color:#176757;border:1px solid #bbd0c5}figure{margin:26px 0}img{max-width:100%;height:auto;border-radius:12px}figcaption,.small{font-size:14px;color:#596f65}.note{padding:18px 22px;border-left:4px solid #b88832;background:#fff5de;margin:24px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}.card{padding:22px;background:white;border:1px solid #d5e1d8;border-radius:12px}table{border-collapse:collapse;width:100%;background:white;font-size:15px}td,th{text-align:left;padding:12px;border-bottom:1px solid #d6e0d9}li{margin:10px 0}.scroll{overflow:auto}@media(max-width:720px){.grid{grid-template-columns:1fr}}@media print{body{background:white}main{padding:0}.downloads,nav{display:none}.card,figure,table{break-inside:avoid}h2{break-after:avoid}a{color:inherit}}
</style></head><body><main>
<nav><a href="/reports/">Gas City Reports</a><a href="../monitor/">Live temperature</a><a href="../../solar-sensor/usb-wiring/">Wiring guide</a></nav>
<p class="eyebrow">Water-temperature · Enclosure R1 · October 13, 2026</p>
<h1>One board. Two cable entries.<br>A saddle for the pipe.</h1>
<p>A black-PETG enclosure for the continuously powered C6 and temperature-probe adapter. The grey <strong>Scanstrut DS16-P</strong> keeps the USB cable intact; the existing <strong>PG7</strong> takes the probe cable out the opposite end.</p>
<div class="chips"><span>2.75″ / 69.85 mm pipe</span><span>70 × 30 mm perfboard</span><span>X2D · 0.4 mm</span><span>One plate · four parts</span></div>
<div class="downloads" style="margin-top:24px"><a href="bambu/water-temperature-R1-black-PETG-X2D.3mf" download>Download X2D project</a><a class="secondary" href="water-temperature-R1-CAD.zip" download>STEP / STL + source</a><a class="secondary" href="gasket-template.pdf">Paper gasket template</a><a class="secondary" href="models/gasket-tracer.stl" download>3D-print gasket tracing plate</a></div>
<p class="small">Native slice: <strong>9 h 37 min · 184.4 g</strong>. Reopened and resliced in Bambu Studio 2.8.2.61; embedded meshes match the CAD exports. Physical fit and sealing remain to be checked.</p>
<figure><img src="images/assembled.png" alt="Black case on a grey pipe, grey USB cable seal at the near end and opposite cable exit"><figcaption>Actual case and saddle meshes. Orange lines illustrate the zip-tie route. The pipe and purchased cable seal are clearance envelopes; the grey cylinder is not a printable gland.</figcaption></figure>
<div class="note"><strong>Two details before printing:</strong> the black spool's brand and temperature label are unknown, so this uses Bambu Generic PETG: <strong>255°C nozzle, 70°C bed, up to 270°C purge</strong>. Check the spool and select its actual AMS slot. The DS16 mounting holes must be marked from the purchased base and drilled after printing; the manufacturer does not dimension their centers.</div>
<h2>The layout</h2><img src="layout.svg" alt="Dimensioned top-view layout of board, USB plug, glands and tie positions">
<div class="grid"><section class="card"><h2 style="margin-top:0">Room for the existing board</h2><p>Four posts retain the fitted <strong>66 × 26 mm</strong> hole pattern. The board sits 9 mm above the outside floor. Its 30 mm populated height has <strong>8.2 mm</strong> clearance to the lid.</p><p>The USB plug extends <strong>25 mm</strong> beyond the short board end, with another <strong>22 mm</strong> for the cable before the USB wall.</p></section><section class="card"><h2 style="margin-top:0">Ties stay below the lid</h2><p>Two saddles, 84 mm apart, match the pipe with a <strong>1 mm rubber liner</strong>. Their 9 × 3.5 mm tunnels accept ties up to 7.6 mm wide and 2 mm thick.</p><p>The closed case is <strong>154 × 76 × 50.2 mm</strong> including screw ears; saddles extend 18 mm below it. Open the lid without cutting the ties.</p></section></div>
<figure><img src="images/interior.png" alt="Open enclosure with perfboard mounted on its four posts"><figcaption>The large empty bay at the USB end allows plug and cable clearance. Large side bosses receive the saddle screws from below; their pilots stop short of the cavity.</figcaption></figure>
<h2>Parts to have ready</h2><div class="scroll"><table><thead><tr><th>Qty</th><th>Hardware</th><th>Use</th></tr></thead><tbody>
<tr><td>4</td><td>M1.7 × 6 mm self-tapping pan-head screws for plastic</td><td>Perfboard; no washers</td></tr>
<tr><td>4</td><td><strong>#4 × ½″</strong> self-tapping pan-head screws (metric: M3 × 12 mm) + 0.5 mm flat washers</td><td>Lid</td></tr>
<tr><td>4</td><td><strong>#4 × ⅝″</strong> self-tapping pan-head screws (metric: M3 × 16 mm) + 0.5 mm flat washers</td><td>Saddles; head ≤6 mm, washer OD ≤7 mm</td></tr>
<tr><td>1 + 1</td><td>Grey Scanstrut DS16-P kit + existing PG7 gland</td><td>USB and probe entry, respectively</td></tr>
<tr><td>2</td><td>Outdoor UV-resistant zip ties, ≥350 mm long, ≤7.6 × 2 mm</td><td>Around the pipe, through the saddle tunnels</td></tr>
<tr><td>2</td><td>1 mm EPDM strips, approximately 28 × 60 mm</td><td>Between saddles and pipe</td></tr>
<tr><td>1</td><td>One-piece 1/16″ (~1.6 mm) closed-cell foam gasket</td><td>Lid; adhesive on one face; use the template</td></tr></tbody></table></div>
<p class="small">Printed pilots need the matching self-tapping screw family, not drill-point screws. Nominal tip clearances with the original metric screws: board 0.8 mm, lid 1.7 mm, saddles 1.0 mm. Check engagement gently by hand; do not bottom out or split the posts.</p>
<p><strong>Buying imperial screws:</strong> choose stainless Phillips pan-head, pointed-tip self-tapping sheet-metal screws: four #4 × ½″ for the lid and four #4 × ⅝″ for the saddles. Keep the specified washers and head-size limits. #4 is about 2.85 mm diameter, slightly smaller than M3; its grip in the printed 2.6 mm pilots is untested. Try one gently by hand and stop if it spins without tightening. Do not enlarge the pilots for #4 or substitute #6 (about 3.5 mm) without revising the holes. Avoid self-drilling tips and countersunk heads. These substitutions apply only to the lid and saddles; use the supplied DS16 fasteners. <a href="https://shop.totallystainless.com/2010catalog/catalog46.pdf">Screw diameter reference</a>.</p>
<h2>Rigid gasket tracing plate</h2><p>Prefer tracing plastic? <a href="models/gasket-tracer.stl" download>Download the tracing plate STL</a> (<a href="models/gasket-tracer.step">STEP</a>). This flat, open-center ring is <strong>152 × 58 × 2 mm</strong>, with the same inner and outer outlines as the foam gasket. Import into Bambu Studio in millimetres at <strong>100% scale</strong>, lay flat, and print in PETG at 0.20 mm layers with 5 top and 5 bottom layers; no supports. It is a separate print from the four-part enclosure project. Remove any brim or edge burrs before tracing.</p><p>Hold the ring flat on the foam backing and trace both edges with a fine pencil. Cut to the traced boundaries; the wider end faces the grey DS16 gland. Check the printed outside measures 152 × 58 mm. <strong>This is a tracing tool, not the installed gasket:</strong> use the cut 1/16″ closed-cell foam to seal the lid.</p>
<h2>Assembly order</h2><ol>
<li><strong>Dry-fit the print.</strong> Remove brims and strings. Check the board holes, lid lip and screw engagement. The intact molded USB plug must pass through the DS16's 16 mm opening.</li>
<li><strong>Mark the DS16 mounting holes from its actual base.</strong> With electronics removed, center it over the larger end opening, then mark and drill the three mounting pilots through the 13 mm wall. The manufacturer suggests 2.5 mm pilots for the No. 4 screws in hard material; verify gentle fit in PETG. Its 36.5 mm drawing dimension is the base diameter, not the bolt circle. Use the supplied gasket and the manufacturer's silicone instructions at the screws. Clean out every chip.</li>
<li><strong>Fit both glands and cables.</strong> DS16 at the thicker USB wall; PG7 at the opposite 2.4 mm wall. Use the DS16 bung that fits the cable jacket, following its instructions. Each gland grips one intact round jacket. No USB cable cutting is required.</li>
<li><strong>Attach the saddles before mounting on the pipe.</strong> #4 × ⅝″ (or M3 × 16) screws and washers go through the recessed underside holes into the case's blind pilots. Then fit the perfboard with M1.7 × 6 screws, plug in USB, and connect the probe wires. Verify a live reading.</li>
<li><strong>Fit the foam gasket and lid.</strong> Use the rigid tracing plate, or print the paper template at 100% and check its 50 mm line, then cut one foam ring. The wider end goes toward DS16. Attach it to the body rim. Orient the lid lip to match the thick USB wall and tighten #4 × ½″ (or M3 × 12) screws evenly until the four stops seat. The 1.2 mm gap gives nominal 25% foam compression.</li>
<li><strong>Mount to the pipe.</strong> Place one 1 mm EPDM strip in each saddle. Thread each tie through its tunnel and around the pipe; keep its head outside the tunnel. Leave slack and drip loops in both cables. Recheck readings after closing.</li></ol>
<div class="grid"><figure><img src="images/saddle.png" alt="Saddle underside with curved pipe seat, two recessed mounting holes and tie tunnel"><figcaption>Curved pipe seat, recessed screw access and separate tie tunnel.</figcaption></figure><figure><img src="images/plate-1.png" alt="One X2D plate with body, lid and two upright saddles"><figcaption>Print poses are saved. The saddles stand on their axial ends.</figcaption></figure></div>
<h2>Checked, and still to check</h2><p>CAD checks passed for all solids, watertight meshes, component clearances, pipe fit allowance, tie passage and screw access. The native Bambu project passed its reopen/reslice check, all four embedded meshes match the STLs, and the plate has no warnings.</p>
<p>Physical fit, seal performance, hot-sun temperature and long-term PETG/tie strength are untested. A gland's IP rating does not certify the printed enclosure. Test sealing with electronics removed before relying on it outdoors. For USB recovery, remove the lid and unplug the cable at the C6; routine updates stay wireless.</p>
<p class="small">Native offscreen preview failed with “X11: The DISPLAY environment variable is missing”; the project includes an actual-CAD preview instead. Stock reserved-tool diagnostics T65279/T65535 remain, with unchanged machine G-code.</p>
<p><a href="README.md">Detailed build notes and reproduction commands</a> · <a href="models/validation.json">CAD validation</a> · <a href="bambu/project-validation.json">Project validation</a></p>
<footer class="small">Hardware dimensions: <a href="https://www.scanstrut.com/marine/cable-seal/vertical/ds16-p">Scanstrut DS16-P</a> · <a href="https://www.scanstrut.com/file/inline/upload/Cable_Seals/DS16-P/DS16-P-Cable-Seal-Technical-_Drawing.pdf">Manufacturer drawing</a> · <a href="https://www.scanstrut.com/file/inline/upload/Cable_Seals/DS16-P/DS21_DS16_Installation_Instructions_-_Issue_1.pdf">Installation instructions</a>. Enclosure R1 · Black PETG · Original solar enclosure preserved.</footer>
</main></body></html>'''
    (ROOT/'index.html').write_text(html)
    print('Generated guide, layout, physical-scale PDF/SVG gasket templates and CAD archive')


if __name__=='__main__':main()
