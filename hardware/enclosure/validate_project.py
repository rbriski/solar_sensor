#!/usr/bin/env python3
"""Compare every saved/round-tripped Bambu mesh with the current print STL."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import numpy as np
from scipy.spatial import cKDTree
import trimesh

ROOT = Path(__file__).resolve().parent
COUNTS = Counter(base=1, lid=1, tray=1, panel_frame=1, panel_spacer=4, panel_clip=4, probe_arm=1)
NS = {'c': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02',
      'p': 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06'}
KEYS = ['printer_model', 'nozzle_diameter', 'curr_bed_type', 'nozzle_temperature',
        'nozzle_temperature_initial_layer', 'textured_plate_temp', 'textured_plate_temp_initial_layer',
        'wall_loops', 'layer_height', 'sparse_infill_density', 'sparse_infill_pattern',
        'top_shell_layers', 'bottom_shell_layers', 'brim_width', 'enable_support']


def check_archive(path):
    with ZipFile(path) as z:
        assert z.testzip() is None
        settings = json.loads(z.read('Metadata/project_settings.config'))
        config = ET.fromstring(z.read('Metadata/model_settings.config'))
        assert len(config.findall('plate')) == 4
        root = ET.fromstring(z.read('3D/3dmodel.model'))
        resources = {o.get('id'): o for o in root.findall('c:resources/c:object', NS)}
        counts = Counter()
        for obj in config.findall('object'):
            part = obj.find('part')
            source = next(m.get('value') for m in part.findall('metadata') if m.get('key') == 'source_file')
            name = Path(source).stem
            counts[name] += 1
            component = resources[obj.get('id')].find('c:components/c:component', NS)
            meshfile = component.get('{'+NS['p']+'}path').lstrip('/')
            model = ET.fromstring(z.read(meshfile))
            verts = np.array([[float(v.get(c)) for c in ('x','y','z')] for v in model.findall('.//c:vertex', NS)])
            faces = np.array([[int(f.get(c)) for c in ('v1','v2','v3')] for f in model.findall('.//c:triangle', NS)])
            embedded = trimesh.Trimesh(vertices=verts, faces=faces)
            expected = trimesh.load_mesh(ROOT / 'models' / (name+'.stl'))
            assert embedded.is_watertight and embedded.is_winding_consistent, name
            assert len(embedded.faces) == len(expected.faces), name
            assert np.allclose(embedded.extents, expected.extents, atol=1e-5), name
            assert abs(embedded.volume-expected.volume) < .05, name
            a = embedded.vertices - embedded.bounds.mean(axis=0)
            b = expected.vertices - expected.bounds.mean(axis=0)
            assert cKDTree(a).query(b)[0].max() < 1e-5, name
            assert cKDTree(b).query(a)[0].max() < 1e-5, name
        assert counts == COUNTS, counts
        gcodes = [n for n in z.namelist() if re.fullmatch(r'Metadata/plate_\d+\.gcode', n)]
        assert len(gcodes) == 4
        for name in gcodes:
            nozzle, bed, flush = set(), set(), set()
            for raw in z.read(name).decode().splitlines():
                line = raw.split(';')[0].strip()
                cmd = line.split(' ')[0]
                s = re.search(r'\bS(-?\d+(?:\.\d+)?)', line)
                t = re.search(r'\bT(-?\d+(?:\.\d+)?)', line)
                if cmd in ('M104','M109') and s: nozzle.add(float(s[1]))
                if cmd in ('M140','M190') and s: bed.add(float(s[1]))
                if cmd in ('M620.10','G150','G383') and t: flush.add(float(t[1]))
            assert max(nozzle) == 240 and bed == {0,75,80} and max(flush) == 240, name
        return settings


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project', type=Path, default=ROOT/'bambu/solar-enclosure-X2D.3mf')
    ap.add_argument('--roundtrip', type=Path, help='Optional reopened.3mf from a native reopen/reslice')
    args = ap.parse_args()
    a = check_archive(args.project)
    audit_path = args.project.with_name('project-validation.json')
    audit = json.loads(audit_path.read_text())
    assert audit['sha256'] == hashlib.sha256(args.project.read_bytes()).hexdigest()
    if args.roundtrip:
        b = check_archive(args.roundtrip)
        for k in KEYS: assert a[k] == b[k], k
        result = json.loads(args.roundtrip.with_name('result.json').read_text())
        assert result['return_code'] == 0 and len(result['sliced_plates']) == 4
        assert sum(len(p['objects']) for p in result['sliced_plates']) == 13
        assert all(not p['warning_message'] for p in result['sliced_plates'])
        audit.update(reopened_and_resliced=True, roundtrip_settings_preserved=True,
                     roundtrip_temperature_audit='Maximum nozzle/flush 240 C; bed 80/75 C')
    audit['embedded_meshes_match_current_STLs'] = True
    audit_path.write_text(json.dumps(audit, indent=2)+'\n')
    print('PASS: all 13 current meshes, four plates, saved settings and temperature limits')


if __name__ == '__main__': main()
