#!/usr/bin/env python3
"""Render the actual generated meshes, not an illustrative approximation."""
from pathlib import Path
import json
import argparse
import vtk

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"models"
REPORT=ROOT.parents[1]/"docs"/"images"


def actor(name,colour,offset=(0,0,0),flip=False):
    r=vtk.vtkSTLReader();r.SetFileName(str(OUT/f"{name}.stl"));r.Update()
    tr=vtk.vtkTransform();tr.PostMultiply()
    if flip:
        tr.Translate(0,-76,0);tr.RotateX(180);tr.Translate(0,76,0)
    tr.Translate(*offset)
    f=vtk.vtkTransformPolyDataFilter();f.SetInputConnection(r.GetOutputPort());f.SetTransform(tr);f.Update()
    normals=vtk.vtkPolyDataNormals();normals.SetInputConnection(f.GetOutputPort());normals.SetFeatureAngle(40)
    mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(normals.GetOutputPort())
    a=vtk.vtkActor();a.SetMapper(mapper);a.GetProperty().SetColor(*colour)
    a.GetProperty().SetSpecular(.18);a.GetProperty().SetSpecularPower(22)
    return a


def block(bounds,colour):
    c=vtk.vtkCubeSource();c.SetBounds(*bounds)
    m=vtk.vtkPolyDataMapper();m.SetInputConnection(c.GetOutputPort())
    a=vtk.vtkActor();a.SetMapper(m);a.GetProperty().SetColor(*colour)
    return a


def render(filename,actors,camera,focus,size=(1600,1100),scale=155):
    renderer=vtk.vtkRenderer();renderer.SetBackground(.947,.965,.969)
    for a in actors:renderer.AddActor(a)
    cam=renderer.GetActiveCamera();cam.SetPosition(*camera);cam.SetFocalPoint(*focus);cam.SetViewUp(0,0,1)
    if camera[0:2]==focus[0:2]:cam.SetViewUp(0,1,0)
    cam.ParallelProjectionOn();cam.SetParallelScale(scale)
    win=vtk.vtkRenderWindow();win.SetOffScreenRendering(1);win.AddRenderer(renderer);win.SetSize(*size);win.SetMultiSamples(8)
    win.Render();img=vtk.vtkWindowToImageFilter();img.SetInput(win);img.SetScale(1);img.Update()
    writer=vtk.vtkPNGWriter();writer.SetFileName(str(REPORT/filename));writer.SetInputConnection(img.GetOutputPort());writer.Write();win.Finalize()


def main():
    global REPORT
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",type=Path,default=ROOT/"bambu/plates.json")
    ap.add_argument("--output",type=Path,default=REPORT)
    args=ap.parse_args()
    REPORT=args.output
    REPORT.mkdir(parents=True,exist_ok=True)
    pale=(.79,.83,.86); blue=(.15,.36,.43); green=(.12,.44,.30)
    exploded=[actor("base",pale),actor("tray",blue,(0,0,58)),actor("lid",pale,(0,0,108),True),
              actor("panel_frame",blue,(0,0,158)),actor("probe_arm",blue,(164,110,5)),
              block((17,147,1,151,175,177.5),(.035,.12,.20))]
    for x,y in ((10,10),(154,10),(10,142),(154,142)):
        exploded.append(actor("panel_spacer",blue,(x,y,116)))
    exploded += [block((60,123,21,54,70.4,72),green),block((60,130,62,92,66.4,67.9),(.65,.49,.25)),
                 block((76,130,99,132,62,72),(.67,.70,.74))]
    render("cad-exploded.png",exploded,(420,-390,365),(130,76,84),scale=143)
    closed=[actor("base",pale),actor("lid",pale,(0,0,46),True),actor("panel_frame",blue,(0,0,71)),
            actor("probe_arm",blue,(164,110,5)),block((17,147,1,151,74,76.5),(.035,.12,.20))]
    for x,y in ((10,10),(154,10),(10,142),(154,142)):
        closed.append(actor("panel_spacer",blue,(x,y,46)))
    render("cad-assembled.png",closed,(410,-365,285),(149,76,26),size=(1600,900),scale=116)
    tray=[actor("tray",blue),block((60,123,21,54,12.4,14),green),block((60,130,62,92,8.4,9.9),(.65,.49,.25)),
          block((76,130,99,132,4,14),(.67,.70,.74))]
    render("cad-tray.png",tray,(330,-265,420),(82,76,5),size=(1300,1000),scale=91)
    manifest=args.manifest
    if manifest.exists():
        for i,plate in enumerate(json.loads(manifest.read_text())["plates"],1):
            actors=[block((0,256,0,256,-1,0),(.87,.89,.90))]
            for item in plate["objects"]:
                actors.append(actor(Path(item["path"]).stem,(.40,.54,.59),
                    (item["pos_x"][0],item["pos_y"][0],item["pos_z"][0])))
            render(f"plate-{i}.png",actors,(380,-400,800),(128,128,0),size=(1000,1000),scale=190)
    print("Rendered actual CAD previews")


if __name__=="__main__":main()
