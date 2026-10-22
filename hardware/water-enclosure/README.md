# Water-temperature pipe enclosure R1

[Build guide and diagrams](index.html) · [X2D project](bambu/water-temperature-R1-black-PETG-X2D.3mf) · [Live Gas City guide](https://gascity.tail96374b.ts.net/reports/water-temperature/enclosure/)

Separate enclosure for the continuously USB-powered XIAO ESP32-C6 and DS18B20 adapter on the existing 70 × 30 mm perfboard. The original solar enclosure is unchanged. The purchased **grey Scanstrut DS16-P** is the USB entry; the existing PG7 gland is the probe entry. Both cables follow the pipe axis and leave opposite short ends. Two ties pass through separate saddles and around the pipe, perpendicular to the cables. The lid can be removed with the ties in place.

## Print and fit

Open the 3MF as a project in Bambu Studio. One plate contains the body, lid and two identical saddles. Saved setup: **X2D, standard 0.4 mm nozzle, Textured PEI, black Generic PETG**, 0.20 mm layers, 6 walls, 6 top/bottom layers, 25% gyroid, 6 mm brim, no supports, 8 mm³/s flow cap. Body upright, lid outside-face-down, saddles on their axial ends. Do not auto-orient the saddles onto their curved surfaces.

The official Generic PETG profile uses **255°C nozzle / 70°C bed**, with a **270°C purge command** in the stock X2D startup sequence. The user confirmed black PETG but did not supply a brand or temperature label; this is not a calibrated spool profile. Match the spool's permitted range and actual printer/AMS slot, then reslice if needed. Do not apply the white solar PETG label to this black spool. Native sliced estimate: **9 h 37 min, 184.4 g** including brims/startup.

| Fit | Dimension |
| --- | --- |
| Case shell, excluding screw ears | 154 × 60 × 46 mm |
| Closed case, including ears | 154 × 76 × 50.2 mm |
| Case plus saddles, bottom to lid | 68.2 mm |
| Perfboard / mounting centers | 70 × 30 mm / 66 × 26 mm |
| Board underside / total populated height | 9 mm above case underside / 30 mm |
| Clearance above populated board | 8.2 mm to lid's inside face |
| Plug projection beyond PCB's USB short end | 25 mm; another 22 mm for flexible cable |
| Pipe OD | 69.85 mm (2.75 in), plus a 1 mm rubber liner |
| Saddle seat radius / spacing along pipe | 35.925 mm / 84 mm |
| Tie channel / checked tie size | 9 × 3.5 mm / 7.6 × 2 mm |
| USB entry | DS16-P: 39 mm shell, 19 mm projection; printed passage 16.2 mm |
| USB wall | 13 mm, with no guessed screw-hole pattern |
| Probe entry | PG7: 13.2 mm hole through 2.4 mm wall |

## Hardware

| Quantity | Item | Purpose |
| --- | --- | --- |
| 4 | M1.7 × 6 mm pan-head **self-tapping screws for plastic** | Perfboard; same nominal fitted solar-board mounting arrangement |
| 4 | **#4 × ½ inch** pan-head self-tapping sheet-metal screws, or M3 × 12 mm self-tapping screws for plastic + M3 flat washers, about 0.5 mm thick | Lid |
| 4 | **#4 × ⅝ inch** pan-head self-tapping sheet-metal screws, or M3 × 16 mm self-tapping screws for plastic + M3 flat washers, about 0.5 mm thick | Saddles into blind case pilots; head ≤6 mm, washer OD ≤7 mm |
| 1 | Purchased Scanstrut DS16-P kit, grey | USB cable seal, with its supplied base gasket and fasteners |
| 1 | Existing PG7 gland with panel washer and locknut | Probe cable |
| 2 | UV-resistant outdoor cable ties, ≥350 mm long, ≤7.6 mm wide and ≤2 mm thick | Pipe mounting; heads stay outside the saddle channels |
| 2 | 1 mm EPDM rubber strips, about 28 × 60 mm | Between the curved saddles and pipe; do not fold/double them |
| 1 | Continuous gasket cut from 1/16 in (about 1.6 mm) **closed-cell foam**, adhesive on one side | Lid; use the full-size template |

Screws above form threads in printed pilots, not metal nuts. Use the matching self-tapping thread family; do not substitute drill-point screws. PCB thickness is modeled as 1.5 mm. Nominal pilot diameters/depths: board 1.3/5.3 mm, lid 2.6/9 mm, saddles 2.6/7.5 mm. With the original metric screws, calculated tip clearance is respectively 0.8, 1.7 and 1.0 mm with the specified stacks. Check real screws and print shrinkage by hand; stop if they bottom out or split the plastic. The saddle pilot roofs retain 1.5 mm of material, separating the screws from the cavity.

For the imperial alternatives, choose stainless Phillips pan-head, pointed-tip self-tapping sheet-metal screws and retain the specified washers/head-size limits. #4 is about 2.85 mm diameter, slightly smaller than M3: grip in the printed 2.6 mm pilots is untested. Try one gently by hand; stop if it spins without tightening. Do not enlarge the pilots for #4 or substitute #6 (about 3.5 mm) without revising the holes. Avoid self-drilling tips and countersunk heads. With nominal 0.5 mm washers, the ½-inch lid screws leave about 1.0 mm tip clearance, and the ⅝-inch saddle screws about 1.1 mm. These alternatives apply only to the lid and saddles; retain the supplied DS16 fasteners. [Screw diameter reference](https://shop.totallystainless.com/2010catalog/catalog46.pdf).

## Rigid gasket tracing plate

[Download the tracing plate STL](models/gasket-tracer.stl) or [STEP](models/gasket-tracer.step). This is a 152 × 58 × 2 mm open-center ring using the exact enclosure gasket outline, including its offset opening. Import in millimetres at 100% scale and print flat in PETG: 0.20 mm layers, 5 top and 5 bottom layers, no supports. Print separately from the four-part enclosure project. Remove brim and edge burrs, confirm the outside measures 152 × 58 mm, then hold it flat on the foam backing and trace both edges with a fine pencil. The wider end faces DS16. Install the cut 1/16-inch closed-cell foam, not this rigid plastic tool.

Regenerate with `python build_gasket_tracer.py` after installing the CAD dependencies. The generator checks the exact gasket area, opening dimensions/offset, solid validity, mesh dimensions and watertightness.

## Assembly

1. Remove brims and strings. Dry-fit board, lid lip, screws, USB connector and PG7. The USB cable's molded plug must pass through the DS16's **16 mm** hardware opening; its 25 mm length does not establish its cross-section. Select the DS16 bung matching the cable jacket, using its included blank if necessary, following the manufacturer instructions.
2. With electronics removed, center the DS16 base over the USB opening. Use the **actual base as the drilling template** for its three mounting holes. Its published 36.5 mm dimension is the base diameter, **not the bolt circle**. Start with the manufacturer's **2.5 mm hard-material pilot** recommendation for the supplied No. 4 screws; verify gentle engagement in this PETG. Drill through the 13 mm wall with an empty case and deburr/clean completely. The supplied No. 4 × 16 mm screws can protrude slightly inside; they remain in the empty USB cable bay. Do not drill the three holes used by the DS16's own cover screws. Follow its instructions for the base gasket and silicone at the mounting screws. Retain the supplied M3 × 10 cover bolts for the gland itself.
3. Install PG7 with its panel seal outside and locknut inside. Feed the probe cable through it. Pass the intact USB plug through the disassembled DS16 housing and case, fit the split bung around the cable, and assemble the seal. Each seal grips one intact, round cable jacket. Do not cut the USB cable.
4. Attach both saddles to the empty case: #4 × ⅝-inch (or M3 × 16) screws and washers go up through the two recessed holes in each saddle into the case's blind underside pilots. Attach before placing the case on the pipe. No screw enters the electronics cavity.
5. Mount the perfboard on the four small posts, USB short end toward DS16, with four M1.7 × 6 screws and **no washers** in this stack. Plug USB into the C6 and route the probe wires to its existing terminal. Check temperature reporting before closing.
6. Cut one lid gasket using the [rigid tracing plate](models/gasket-tracer.stl), or [gasket-template.pdf](gasket-template.pdf), printed at **100% / Actual size**; verify the 50 mm scale line. The gasket is asymmetric: its wider end goes toward DS16. Adhere to the body rim without covering the cavity, locator lip or screw stops. Nominal closed gap is 1.2 mm, about 25% compression of 1.6 mm foam. Solid rubber or 3 mm foam will not have the same fit.
7. Place the lid with its offset lip aligned to the thicker USB wall. Fit four #4 × ½-inch (or M3 × 12) screws and washers. Tighten evenly and gently until the four stops seat. Do not force a reversed lid or crush the foam flat.
8. Put one 1 mm EPDM strip in each saddle. Thread a tie through each saddle tunnel and around the 2.75-inch pipe; tighten with the head outside the tunnel. Keep the lid, glands and cables clear. Leave a little cable slack and external drip loops so the USB plug is not pulled sideways.

For recovery, open the lid and unplug USB at the C6. The gland stays attached to the cable. Routine updates are wireless.

## Validation and limits

The generator checks valid single solids, watertight STL meshes, all printed-part intersections, PCB/component/USB/pipe/gland/gasket clearances, tie passage and mounting screw envelopes. The project audit compares all four embedded meshes to the print STLs, checks print poses, plate margins and brim spacing, verifies saved printer/material/process settings and generated temperatures, then repeats after a native Bambu reopen/reslice. See [geometry checks](models/validation.json) and [project checks](bambu/project-validation.json).

The enclosure has **not been physically fitted or water-tested**. The gland's IP rating does not certify a printed case. Test sealing with electronics removed; check the actual pipe fit, screw engagement and tie grip before installing. Black PETG's hot-sun temperature and long-term creep were not tested. Native offscreen thumbnail rendering reports `X11: The DISPLAY environment variable is missing`; the package includes thumbnails rendered from the actual CAD instead. Stock machine G-code also produces `Invalid T command (T65279)` and `(T65535)` diagnostics; slicing succeeds with no plate warnings, and those reserved commands remain unchanged.

## Rebuild

Use the pinned [CAD dependencies](../enclosure/requirements.txt). Bambu Studio 2.8.2.61 and its matching official profiles were used.

```bash
python build_enclosure.py
python build_gasket_tracer.py
python render.py
python prepare_project.py --profiles /path/to/profiles/BBL --output /tmp/water-build --slicer-output /tmp/water-build
bambu-studio --load-settings '/tmp/water-build/machine.json;/tmp/water-build/process.json' --load-filaments /tmp/water-build/filament.json --load-assemble-list /tmp/water-build/plates.json --arrange 0 --orient 0 --slice 0 --export-3mf water-temperature-R1-black-PETG-X2D.3mf --outputdir /tmp/water-build
python package_project.py --staging /tmp/water-build
bambu-studio --slice 0 --export-3mf reopened.3mf --outputdir /tmp/water-roundtrip bambu/water-temperature-R1-black-PETG-X2D.3mf
python package_project.py --roundtrip /tmp/water-roundtrip/reopened.3mf
python make_guide.py
```

DS16 sources: [manufacturer](https://www.scanstrut.com/marine/cable-seal/vertical/ds16-p), [dimension drawing](https://www.scanstrut.com/file/inline/upload/Cable_Seals/DS16-P/DS16-P-Cable-Seal-Technical-_Drawing.pdf), [assembly instructions](https://www.scanstrut.com/file/inline/upload/Cable_Seals/DS16-P/DS21_DS16_Installation_Instructions_-_Issue_1.pdf), [purchased Amazon item](https://www.amazon.com/dp/B003D4EJLQ). Bambu profile/G-code provenance and third-party licensing follow the repository's [notices](../../THIRD_PARTY_NOTICES.md).
