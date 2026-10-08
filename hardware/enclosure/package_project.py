#!/usr/bin/env python3
"""Package a Bambu-created project, add CAD previews and audit saved settings."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from io import BytesIO
import argparse
import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET
from PIL import Image

ROOT=Path(__file__).resolve().parent
REPORT=ROOT.parents[1]/"docs"/"images"
NAME="solar-enclosure-X2D.3mf"


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--staging",type=Path,required=True)
    ap.add_argument("--name",default=NAME)
    ap.add_argument("--destination",type=Path,default=ROOT/"bambu")
    ap.add_argument("--plate-count",type=int,default=4)
    ap.add_argument("--object-count",type=int,default=13)
    ap.add_argument("--preview-prefix",default="plate-")
    ap.add_argument("--previews",type=Path,default=REPORT)
    args=ap.parse_args()
    dest=args.destination;dest.mkdir(exist_ok=True,parents=True)
    for name in ("machine.json","process.json","filament.json","plates.json","profile-status.json","result.json"):
        shutil.copy2(args.staging/name,dest/name)
    manifest=json.loads((dest/'plates.json').read_text())
    for plate in manifest['plates']:
        for obj in plate['objects']:obj['path']='../models/'+Path(obj['path']).name
    (dest/'plates.json').write_text(json.dumps(manifest,indent=2)+'\n')
    audit={"slicer":"Bambu Studio 2.8.2.61","all_plates_sliced":False,"plate_count":args.plate_count,
           "object_count":args.object_count,"temperature_commands":{},"setup":{"printer":"Bambu Lab X2D","nozzle_mm":0.4,"bed":"Textured PEI"},
           "limitations":["0.4 mm standard nozzle and Textured PEI are stated setup assumptions.",
                          "Settings match the supplied white PETG label; no physical flow calibration is claimed.",
                          "Interactive GUI not tested; project is reopened and sliced with native Bambu CLI.",
                          "Native offscreen thumbnails failed; included thumbnails are rendered from the actual CAD and plate manifest.",
                          "Console diagnostics for stock reserved T65279/T65535 remain; machine G-code was not altered."]}
    result=json.loads((dest/"result.json").read_text())
    assert result["return_code"]==0 and len(result["sliced_plates"])==args.plate_count
    assert sum(len(p["objects"]) for p in result["sliced_plates"])==args.object_count
    audit["all_plates_sliced"]=True
    audit["estimates"]=[]
    for p in result["sliced_plates"]:
        assert not p["warning_message"],p["warning_message"]
        audit["estimates"].append({"plate":p["id"],"seconds":round(p["total_predication"]),
              "grams":round(sum(f["total_used_g"] for f in p["filaments"]),1)})
    with ZipFile(args.staging/args.name) as original,ZipFile(dest/args.name,"w",ZIP_DEFLATED,compresslevel=6) as target:
        settings=json.loads(original.read("Metadata/project_settings.config"))
        assert settings["printer_model"]=="Bambu Lab X2D"
        assert settings["curr_bed_type"]=="Textured PEI Plate"
        for key in ("nozzle_temperature","nozzle_temperature_initial_layer","filament_flush_temp"):
            assert all(float(v)==240 for v in settings[key]),(key,settings[key])
        assert settings["textured_plate_temp_initial_layer"]==["80"]
        assert settings["textured_plate_temp"]==["75"]
        assert settings["wall_loops"]=="6" and settings["enable_support"]=="0"
        models=ET.fromstring(original.read("Metadata/model_settings.config"))
        plates=models.findall("plate");assert len(plates)==args.plate_count
        for idx,p in enumerate(plates,1):
            for elem in p.findall("metadata"):
                if elem.get("key")=="filament_map_mode":elem.set("value","Manual")
            ET.SubElement(p,"metadata",key="thumbnail_file",value=f"Metadata/plate_{idx}.png")
        for info in original.infolist():
            if info.filename=="Metadata/model_settings.config":
                target.writestr(info,ET.tostring(models,encoding="UTF-8",xml_declaration=True));continue
            data=original.read(info.filename)
            if info.filename.endswith(".gcode"):
                temperatures={"nozzle":set(),"bed":set(),"flush":set()}
                for raw in data.decode().splitlines():
                    line=raw.split(";")[0].strip()
                    command=line.split(" ")[0]
                    sm=re.search(r"\bS(-?\d+(?:\.\d+)?)",line)
                    tm=re.search(r"\bT(-?\d+(?:\.\d+)?)",line)
                    if command in ("M104","M109") and sm:temperatures["nozzle"].add(float(sm[1]))
                    if command in ("M140","M190") and sm:temperatures["bed"].add(float(sm[1]))
                    if command=="M620.10" and tm:temperatures["flush"].add(float(tm[1]))
                assert max(temperatures["nozzle"])==240,temperatures
                assert temperatures["bed"]=={0,75,80},temperatures
                assert temperatures["flush"]=={240},temperatures
                audit["temperature_commands"][info.filename]={k:sorted(v) for k,v in temperatures.items()}
            target.writestr(info,data)
        for i in range(1,args.plate_count+1):
            img=Image.open(args.previews/f"{args.preview_prefix}{i}.png").convert("RGBA")
            for suffix,size in (("",512),("_small",128)):
                resized=img.resize((size,size),Image.Resampling.LANCZOS);b=BytesIO();resized.save(b,"PNG")
                target.writestr(f"Metadata/plate_{i}{suffix}.png",b.getvalue())
    with ZipFile(dest/args.name) as z:
        assert z.testzip() is None
        ns={"r":"http://schemas.openxmlformats.org/package/2006/relationships"}
        for rel in ET.fromstring(z.read("_rels/.rels")).findall("r:Relationship",ns):
            assert rel.attrib["Target"].lstrip("/") in z.namelist(),rel.attrib
    audit["sha256"]=hashlib.sha256((dest/args.name).read_bytes()).hexdigest()
    (dest/"project-validation.json").write_text(json.dumps(audit,indent=2)+"\n")
    print(json.dumps(audit,indent=2))


if __name__=="__main__":main()
