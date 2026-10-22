#!/usr/bin/env python3
"""Render actual R1 meshes in assembly and print poses."""
from pathlib import Path
import math
import vtk

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'images'
BLACK=(.17,.18,.20)


def mesh(name,colour=BLACK,offset=(0,0,0),flip=False):
    r=vtk.vtkSTLReader();r.SetFileName(str(ROOT/'models'/(name+'.stl')));r.Update()
    tr=vtk.vtkTransform();tr.PostMultiply()
    if flip:tr.RotateX(180)
    tr.Translate(*offset)
    f=vtk.vtkTransformPolyDataFilter();f.SetInputConnection(r.GetOutputPort());f.SetTransform(tr);f.Update()
    normals=vtk.vtkPolyDataNormals();normals.SetInputConnection(f.GetOutputPort());normals.SetFeatureAngle(35)
    m=vtk.vtkPolyDataMapper();m.SetInputConnection(normals.GetOutputPort())
    a=vtk.vtkActor();a.SetMapper(m);a.GetProperty().SetColor(*colour)
    a.GetProperty().SetSpecular(.2);a.GetProperty().SetSpecularPower(24)
    return a


def line(points,colour,radius):
    pts=vtk.vtkPoints()
    for p in points:pts.InsertNextPoint(*p)
    lines=vtk.vtkCellArray();lines.InsertNextCell(len(points))
    for i in range(len(points)):lines.InsertCellPoint(i)
    poly=vtk.vtkPolyData();poly.SetPoints(pts);poly.SetLines(lines)
    tube=vtk.vtkTubeFilter();tube.SetInputData(poly);tube.SetRadius(radius);tube.SetNumberOfSides(24)
    mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(tube.GetOutputPort())
    a=vtk.vtkActor();a.SetMapper(mapper);a.GetProperty().SetColor(*colour);return a


def render(name,actors,camera,focus,scale=110,size=(1500,1000)):
    r=vtk.vtkRenderer();r.SetBackground(.93,.95,.96)
    for a in actors:r.AddActor(a)
    c=r.GetActiveCamera();c.SetPosition(*camera);c.SetFocalPoint(*focus);c.SetViewUp(0,0,1)
    c.ParallelProjectionOn();c.SetParallelScale(scale)
    w=vtk.vtkRenderWindow();w.SetOffScreenRendering(1);w.AddRenderer(r);w.SetSize(*size);w.SetMultiSamples(8)
    w.Render();f=vtk.vtkWindowToImageFilter();f.SetInput(w);f.Update()
    writer=vtk.vtkPNGWriter();writer.SetFileName(str(OUT/(name+'.png')));writer.SetInputConnection(f.GetOutputPort());writer.Write();w.Finalize()


def main():
    OUT.mkdir(exist_ok=True)
    saddles=[mesh('saddle-assembled-reference',offset=(x,0,0)) for x in (-42,42)]
    pipe=mesh('pipe-reference',(.72,.74,.75))
    cables=[line([(-132,0,23),(-70,0,23)],(.08,.09,.10),2),
            line([(75,0,23),(130,0,23)],(.08,.09,.10),2)]
    ties=[]
    for x in (-42,42):
        points=[(x,-31,-3.75),(x,31,-3.75)]
        points += [(x,37*math.cos(t),-44.925+37*math.sin(t)) for t in [-(math.pi*i/40) for i in range(41)]]
        points.append((x,-31,-3.75))
        ties.append(line(points,(.90,.53,.12),.9))
    closed=[mesh('body'),mesh('lid',offset=(0,0,50.2),flip=True),pipe,*saddles,*cables,*ties,
            mesh('ds16_shell-reference',(.65,.66,.67))]
    render('assembled',closed,(-250,-270,210),(0,0,-13),scale=111)
    inside=[mesh('body'),mesh('perfboard-reference',(.61,.43,.19)),
            mesh('lid',offset=(0,0,94),flip=True),pipe,*saddles,
            mesh('ds16_shell-reference',(.65,.66,.67)),*cables]
    render('exploded',inside,(-265,-285,220),(0,0,25),scale=108)
    render('interior',[mesh('body'),mesh('perfboard-reference',(.61,.43,.19))],
           (-180,-190,310),(0,0,19),scale=89)
    render('saddle',[mesh('saddle-assembled-reference')],(-65,-85,-55),(0,0,-8),scale=34)
    plate=[mesh('body',offset=(128,58,0)),mesh('lid',offset=(128,158,0)),
           mesh('saddle',offset=(226,28,0)),mesh('saddle',offset=(226,132,0))]
    render('plate-1',plate,(390,-360,750),(128,112,0),scale=170,size=(1000,1000))
    print('Rendered five views from the exported CAD meshes')


if __name__=='__main__':main()
