#!/usr/bin/env python3
"""Package native Bambu output, then audit every mesh, pose and temperature."""
from collections import Counter
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import argparse
import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial import cKDTree
import trimesh
from PIL import Image

ROOT=Path(__file__).resolve().parent
DEST=ROOT/'bambu'
NAME='water-temperature-R1-black-PETG-X2D.3mf'
NS={'c':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02',
    'p':'http://schemas.microsoft.com/3dmanufacturing/production/2015/06'}
KEYS=['printer_model','nozzle_diameter','curr_bed_type','nozzle_temperature',
      'nozzle_temperature_initial_layer','textured_plate_temp','textured_plate_temp_initial_layer',
      'filament_colour','filament_settings_id','wall_loops','layer_height','sparse_infill_density',
      'sparse_infill_pattern','top_shell_layers','bottom_shell_layers','enable_support','brim_width']


def audit(path):
    with ZipFile(path) as z:
        assert z.testzip() is None
        s=json.loads(z.read('Metadata/project_settings.config'))
        assert s['printer_model']=='Bambu Lab X2D' and s['curr_bed_type']=='Textured PEI Plate'
        assert all(float(x)==.4 for x in s['nozzle_diameter'])
        assert set(s['nozzle_temperature'])=={'255'} and set(s['nozzle_temperature_initial_layer'])=={'255'}
        assert s['textured_plate_temp']==['70'] and s['textured_plate_temp_initial_layer']==['70']
        assert s['filament_colour']==['#161616'] and s['wall_loops']=='6'
        assert s['enable_support']=='0' and s['brim_width']=='6'
        config=ET.fromstring(z.read('Metadata/model_settings.config'))
        assert len(config.findall('plate'))==1
        root=ET.fromstring(z.read('3D/3dmodel.model'))
        resources={o.get('id'):o for o in root.findall('c:resources/c:object',NS)}
        count=Counter();bounds=[]
        for obj in config.findall('object'):
            part=obj.find('part');meta={m.get('key'):m.get('value') for m in part.findall('metadata') if m.get('key')}
            name=Path(meta['source_file']).stem;count[name]+=1
            component=resources[obj.get('id')].find('c:components/c:component',NS)
            model=ET.fromstring(z.read(component.get('{'+NS['p']+'}path').lstrip('/')))
            verts=np.array([[float(v.get(k)) for k in ('x','y','z')] for v in model.findall('.//c:vertex',NS)])
            faces=np.array([[int(f.get(k)) for k in ('v1','v2','v3')] for f in model.findall('.//c:triangle',NS)])
            embedded=trimesh.Trimesh(vertices=verts,faces=faces)
            expected=trimesh.load_mesh(ROOT/'models'/(name+'.stl'))
            assert embedded.is_watertight and embedded.is_winding_consistent,name
            assert len(embedded.faces)==len(expected.faces),name
            assert np.allclose(embedded.extents,expected.extents,atol=1e-5),name
            assert abs(embedded.volume-expected.volume)<.05,name
            a=embedded.vertices-embedded.bounds.mean(axis=0);b=expected.vertices-expected.bounds.mean(axis=0)
            assert cKDTree(a).query(b)[0].max()<1e-5 and cKDTree(b).query(a)[0].max()<1e-5,name
            matrix=np.array([float(x) for x in meta['matrix'].split()]).reshape(4,4)
            assert np.allclose(matrix[:3,:3],np.eye(3)),(name,'unexpected orientation')
            bb=embedded.bounds-embedded.bounds.mean(axis=0)+matrix[:3,3]
            assert abs(bb[0,2])<1e-5 and np.all(bb[0,:2]>=6) and np.all(bb[1,:2]<=250),(name,bb)
            bounds.append((name,bb))
        assert count==Counter(body=1,lid=1,saddle=2),count
        for i,(an,a) in enumerate(bounds):
            for bn,b in bounds[i+1:]:
                gap=np.maximum(b[0,:2]-a[1,:2],a[0,:2]-b[1,:2])
                assert np.any(gap>12),(an,bn,'brim clearance',gap)
        gcodes=[n for n in z.namelist() if re.fullmatch(r'Metadata/plate_\d+\.gcode',n)]
        assert len(gcodes)==1
        temps={k:set() for k in ('nozzle','bed','flush')}
        for raw in z.read(gcodes[0]).decode().splitlines():
            line=raw.split(';')[0].strip();cmd=line.split(' ')[0]
            v=re.search(r'\bS(-?\d+(?:\.\d+)?)',line);t=re.search(r'\bT(-?\d+(?:\.\d+)?)',line)
            if cmd in ('M104','M109') and v:temps['nozzle'].add(float(v[1]))
            if cmd in ('M140','M190') and v:temps['bed'].add(float(v[1]))
            if cmd in ('M620.10','G150','G383') and t:temps['flush'].add(float(t[1]))
        assert max(temps['nozzle'])==255 and temps['bed']=={0,70} and max(temps['flush'])==270,temps
        return s,{k:sorted(v) for k,v in temps.items()}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--staging',type=Path);ap.add_argument('--roundtrip',type=Path)
    args=ap.parse_args();DEST.mkdir(exist_ok=True)
    if args.staging:
        stage=args.staging
        for n in ('machine.json','process.json','filament.json','profile-status.json','result.json'):
            shutil.copyfile(stage/n,DEST/n)
        plates=json.loads((stage/'plates.json').read_text())
        for p in plates['plates']:
            for o in p['objects']:o['path']='../models/'+Path(o['path']).name
        (DEST/'plates.json').write_text(json.dumps(plates,indent=2)+'\n')
        result=json.loads((stage/'result.json').read_text())
        assert result['return_code']==0 and len(result['sliced_plates'])==1
        assert len(result['sliced_plates'][0]['objects'])==4 and not result['sliced_plates'][0]['warning_message']
        with ZipFile(stage/NAME) as src,ZipFile(DEST/NAME,'w',ZIP_DEFLATED,compresslevel=6) as out:
            for item in src.infolist():
                if item.filename in ('Metadata/plate_1.png','Metadata/plate_1_small.png'):continue
                data=src.read(item.filename)
                if item.filename=='Metadata/model_settings.config':
                    root=ET.fromstring(data);p=root.find('plate')
                    ET.SubElement(p,'metadata',key='thumbnail_file',value='Metadata/plate_1.png')
                    data=ET.tostring(root,encoding='UTF-8',xml_declaration=True)
                out.writestr(item,data)
            preview=Image.open(ROOT/'images/plate-1.png').convert('RGBA')
            for suffix,size in [('',512),('_small',128)]:
                buf=BytesIO();preview.resize((size,size),Image.Resampling.LANCZOS).save(buf,'PNG')
                out.writestr('Metadata/plate_1'+suffix+'.png',buf.getvalue())
        with ZipFile(DEST/NAME) as z:
            for r in ET.fromstring(z.read('_rels/.rels')):assert r.get('Target').lstrip('/') in z.namelist()
        plate=result['sliced_plates'][0]
        record=dict(slicer='Bambu Studio 2.8.2.61',plate_count=1,part_count=4,
                    sliced=True,no_plate_warnings=True,seconds=round(plate['total_predication']),
                    grams=round(sum(f['total_used_g'] for f in plate['filaments']),1),
                    limitations=['Physical fit, weather sealing and long-term strength untested.',
                        'Generic black PETG profile is not a measured spool calibration.',
                        'No GUI interaction tested. CAD thumbnail supplied after native offscreen thumbnail failure.',
                        'Stock X2D reserved T65279/T65535 diagnostics retained; machine G-code unchanged.'])
    else:record=json.loads((DEST/'project-validation.json').read_text())
    settings,temps=audit(DEST/NAME)
    record.update(embedded_meshes_match_current_STLs=True,plate_bounds_and_brim_clearance=True,
                  temperature_commands=temps,sha256=hashlib.sha256((DEST/NAME).read_bytes()).hexdigest())
    if args.roundtrip:
        other,other_temps=audit(args.roundtrip)
        for k in KEYS:assert settings[k]==other[k],k
        r=json.loads(args.roundtrip.with_name('result.json').read_text())
        assert r['return_code']==0 and len(r['sliced_plates'])==1 and len(r['sliced_plates'][0]['objects'])==4
        assert not r['sliced_plates'][0]['warning_message']
        record.update(reopened_and_resliced=True,roundtrip_settings_preserved=True,
                      roundtrip_temperatures=other_temps)
    (DEST/'project-validation.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
