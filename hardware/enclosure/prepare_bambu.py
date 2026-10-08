#!/usr/bin/env python3
"""Prepare reproducible Bambu CLI inputs from the installed official profiles.

Material limits come from the supplied white PETG label (225–240 C, bed 70–80 C). The printer setup uses
standard 0.4 mm nozzles and Textured PEI. This is not a measured calibration.
"""
from pathlib import Path
import argparse
import json
import shutil

ROOT=Path(__file__).resolve().parent


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--profiles",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--slicer-output",type=Path,help="Output directory as seen inside an optional slicer container")
    args=ap.parse_args()
    out=args.output
    out.mkdir(parents=True,exist_ok=True)
    profiles={}
    for folder in ("machine","process","filament"):
        for path in (args.profiles/folder).glob("*.json"):
            d=json.loads(path.read_text());profiles[d.get("name",path.stem)]=d

    def resolve(name):
        d=profiles[name]
        result=resolve(d["inherits"]) if d.get("inherits") else {}
        for inc in d.get("include",[]): result.update(resolve(inc))
        result.update(d)
        result.pop("include",None)
        return result

    machine_name="Bambu Lab X2D 0.4 nozzle"
    process_name="0.20mm Standard @BBL X2D"
    filament_name="Generic PETG @BBL X2D 0.4 nozzle"
    for name,source in (("system-machine",machine_name),("system-process",process_name),("system-filament",filament_name)):
        (out/f"{name}.json").write_text(json.dumps(resolve(source),indent=2)+"\n")
    (out/"machine-model.json").write_text(json.dumps(profiles["Bambu Lab X2D"],indent=2)+"\n")
    machine=resolve(machine_name)
    machine["inherits"]=""
    machine["extruder_nozzle_stats"]=["Standard#1","Standard#1"]
    process=resolve(process_name)
    process.update(name="Solar enclosure - White PETG 0.20mm",inherits=process_name,
                   **{"from":"user","wall_loops":"6","top_shell_layers":"6","bottom_shell_layers":"6",
                      "top_shell_thickness":"1.2","bottom_shell_thickness":"1.2","sparse_infill_density":"25%",
                      "sparse_infill_pattern":"gyroid","layer_height":"0.2","initial_layer_print_height":"0.2",
                      "enable_support":"0","brim_type":"outer_only","brim_width":"6","brim_object_gap":"0.15",
                      "wall_generator":"arachne","seam_position":"aligned","top_surface_pattern":"monotonic",
                      "ironing_type":"no ironing","enable_prime_tower":"0","print_sequence":"by layer",
                      "curr_bed_type":"Textured PEI Plate","elefant_foot_compensation":"0.15"})
    # Dual-nozzle profiles have six entries for the supported extruder variants.
    for k,v in dict(outer_wall_speed=45,inner_wall_speed=90,top_surface_speed=30,
                    sparse_infill_speed=100,internal_solid_infill_speed=80,bridge_speed=25,
                    initial_layer_speed=25,initial_layer_infill_speed=40,travel_speed=300,
                    gap_infill_speed=50,default_acceleration=3000,outer_wall_acceleration=1500,
                    top_surface_acceleration=1000,travel_acceleration=5000).items():
        process[k]=[str(v)]*6
    filament=resolve(filament_name)
    filament.update(name="White PETG 225-240C - Solar X2D",inherits=filament_name,
                    **{"from":"user","filament_max_volumetric_speed":["8"]*6,
                       "filament_colour":["#FFFFFF"],"filament_settings_id":["White PETG 225-240C - Solar X2D"],
                       "nozzle_temperature":["240"]*6,"nozzle_temperature_initial_layer":["240"]*6,
                       "nozzle_temperature_range_low":["225"],"nozzle_temperature_range_high":["240"],
                       "textured_plate_temp_initial_layer":["80"],"textured_plate_temp":["75"],
                       "filament_flush_temp":["240"]*6,"filament_flush_temp_fast":["240"],
                       "filament_tower_interface_print_temp":["240"],"filament_preheat_temperature_delta":["0"]*6,
                       "fan_min_speed":["30"],"fan_max_speed":["60"],"overhang_fan_speed":["80"],
                       "first_x_layer_fan_speed":["30"],"additional_cooling_fan_speed":["0"],
                       "close_fan_the_first_x_layers":["3"],"chamber_temperatures":["0"]})
    for name,d in (("machine",machine),("process",process),("filament",filament)):
        (out/f"{name}.json").write_text(json.dumps(d,indent=2)+"\n")

    # Positions are translations of the STL assembly coordinates. Each clone
    # is an independent entry, avoiding CLI clone-position accumulation.
    def obj(name,dx=0,dy=0,params=None):
        d={"path":str((args.slicer_output or out.resolve()) / f"{name}.stl"),"count":1,"filaments":[1],
           "pos_x":[dx],"pos_y":[dy],"pos_z":[0]}
        if params:d["print_params"]=params
        return d
    plates=[
      {"plate_name":"1 - Base","need_arrange":False,"objects":[obj("base",32,52)]},
      {"plate_name":"2 - Lid and spacers","need_arrange":False,"objects":[obj("lid",46,58)]+[
          obj("panel_spacer",x,30) for x in (85,113,141,169)]},
      {"plate_name":"3 - Solar panel frame","need_arrange":False,"objects":[obj("panel_frame",46,52)]},
      {"plate_name":"4 - Tray, clips and probe arm","need_arrange":False,"objects":[
          obj("tray",46,76),obj("probe_arm",48,34)]+[
          obj("panel_clip",x,66) for x in (65,103,141,179)]}
    ]
    for plate in plates:
        plate["plate_params"]={"filament_map_mode":"Manual","filament_map":"1"}
    (out/"plates.json").write_text(json.dumps({"plates":plates},indent=2)+"\n")
    for f in (ROOT/"models").glob("*.stl"):shutil.copy2(f,out/f.name)
    provenance={"slicer_version":"2.8.2.61","profile_source":"https://github.com/bambulab/BambuStudio/tree/v02.08.02.61/resources/profiles/BBL",
                "status":"Configured from supplied filament label; 0.4 mm nozzle and Textured PEI are stated setup assumptions, not measured calibration",
                "printer":"Bambu Lab X2D","nozzle_assumed_mm":0.4,"plate_assumed":"Textured PEI",
                "material_confirmed":"White PETG, 1.75 mm; brand not shown; original filament label",
                "label_nozzle_range_c":[225,240],"label_bed_range_c":[70,80],
                "nozzle_temperature_c":240,"bed_initial_c":80,"bed_other_layers_c":75,
                "plate_count":4,"object_count":13,"layer_height_mm":0.2,"wall_loops":6,
                "top_bottom_layers":6,"infill":"25% gyroid","supports":False,
                "brim_mm":6,"outer_wall_mm_s":45,"max_volumetric_mm3_s":8,
                "temperature_note":"Printing and flushing set to 240 C; stock X2D startup/end G-code retained. Generated temperature commands checked separately."}
    (out/"profile-status.json").write_text(json.dumps(provenance,indent=2)+"\n")
    print(out)


if __name__=="__main__":main()
