#!/usr/bin/env python3
"""Resolve installed Bambu X2D profiles and prepare a four-part, one-plate job."""
from pathlib import Path
import argparse
import json
import shutil

ROOT=Path(__file__).resolve().parent


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--profiles',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--slicer-output',default='/work')
    a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    profiles={}
    for folder in ('machine','process','filament'):
        for f in (a.profiles/folder).glob('*.json'):
            d=json.loads(f.read_text());profiles[d.get('name',f.stem)]=d
    def resolve(name):
        d=profiles[name];out=resolve(d['inherits']) if d.get('inherits') else {}
        for inc in d.get('include',[]):out.update(resolve(inc))
        out.update(d);out.pop('include',None);return out
    machine=resolve('Bambu Lab X2D 0.4 nozzle')
    machine.update(inherits='',extruder_nozzle_stats=['Standard#1','Standard#1'])
    process=resolve('0.20mm Standard @BBL X2D')
    process.update(name='Water enclosure R1 - PETG 0.20mm',inherits='0.20mm Standard @BBL X2D',
       **{'from':'user','wall_loops':'6','top_shell_layers':'6','bottom_shell_layers':'6',
          'top_shell_thickness':'1.2','bottom_shell_thickness':'1.2',
          'sparse_infill_density':'25%','sparse_infill_pattern':'gyroid',
          'layer_height':'0.2','initial_layer_print_height':'0.2',
          'enable_support':'0','brim_type':'outer_only','brim_width':'6','brim_object_gap':'0.15',
          'wall_generator':'arachne','seam_position':'aligned','top_surface_pattern':'monotonic',
          'ironing_type':'no ironing','enable_prime_tower':'0','print_sequence':'by layer',
          'curr_bed_type':'Textured PEI Plate','elefant_foot_compensation':'0.15'})
    for k,v in dict(outer_wall_speed=45,inner_wall_speed=90,top_surface_speed=30,
             sparse_infill_speed=100,internal_solid_infill_speed=80,bridge_speed=25,
             initial_layer_speed=25,initial_layer_infill_speed=40,travel_speed=300,
             gap_infill_speed=50,default_acceleration=3000,outer_wall_acceleration=1500,
             top_surface_acceleration=1000,travel_acceleration=5000).items():process[k]=[str(v)]*6
    filament=resolve('Generic PETG @BBL X2D 0.4 nozzle')
    filament.update(name='Black Generic PETG - Water X2D',inherits='Generic PETG @BBL X2D 0.4 nozzle',
       **{'from':'user','filament_colour':['#161616'],
          'filament_settings_id':['Black Generic PETG - Water X2D'],
          'filament_max_volumetric_speed':['8']*6})
    def obj(name,x,y):
        return dict(path=str(Path(a.slicer_output)/(name+'.stl')),count=1,filaments=[1],
                    pos_x=[x],pos_y=[y],pos_z=[0])
    plates={'plates':[dict(plate_name='Water sensor R1 - body, lid and two saddles',need_arrange=False,
           plate_params={'filament_map_mode':'Manual','filament_map':'1'},
           objects=[obj('body',128,58),obj('lid',128,158),obj('saddle',226,28),obj('saddle',226,132)])]}
    status=dict(slicer_version='2.8.2.61',printer='Bambu Lab X2D',nozzle_mm=.4,
          plate='Textured PEI',material='Black PETG confirmed; brand/label/calibration unknown',
          temperature_basis='Unmodified official Generic PETG X2D temperature settings, not white PETG label',
          nozzle_c=filament['nozzle_temperature'],bed_initial_c=filament['textured_plate_temp_initial_layer'],
          bed_c=filament['textured_plate_temp'],plate_count=1,object_count=4,
          profile_source='https://github.com/bambulab/BambuStudio/tree/v02.08.02.61/resources/profiles/BBL',
          note='Check spool temperature range and select actual AMS slot before printing.')
    for name,d in [('machine',machine),('process',process),('filament',filament),('plates',plates),('profile-status',status)]:
        (a.output/(name+'.json')).write_text(json.dumps(d,indent=2)+'\n')
    for n in ('body','lid','saddle'):shutil.copyfile(ROOT/'models'/(n+'.stl'),a.output/(n+'.stl'))
    print(json.dumps(status,indent=2))


if __name__=='__main__':main()
