import sys; sys.path.append('../../../src'); sys.path.append('./src')
import numpy as np
import code
import solver.DG as Solver
import physics.scalar.scalar as Scalar
import meshing.common as MeshCommon
import processing.post as Post
import processing.plot as Plot
import general
import meshing.gmsh as MeshGmsh
import os
import MeshTools
import processing.readwritedatafiles as ReadWriteDataFiles


### NOTE: STILL NEED TO BE ABLE TO RESTART WITH DIFFERENT BASIS/ORDER AND PROJECT


CurrentDir = os.path.dirname(os.path.abspath(__file__)) + "/"


fname = "Data1.pkl"
mesh, physics, Params, _ = ReadWriteDataFiles.read_data_file(fname)

### Solver parameters
# SolutionBasis = "LagrangeEqTri"
SolutionBasis = "HierarchicH1Tri"
dt = 0.05
InitialTime = 2.5
FinalTime = 10.0
NumTimeSteps = int((FinalTime-InitialTime)/dt + 10.*general.eps)
SolutionOrder = 10
Params = general.set_solver_params(Params, SolutionOrder=SolutionOrder,InitialTime=InitialTime,FinalTime=FinalTime,
								 NumTimeSteps=NumTimeSteps,SolutionBasis=SolutionBasis,TimeStepper="RK4",
								 L2InitialCondition=True,ApplyLimiter=None,WriteInterval=50,
								 RestartFile=fname)

### Solve
solver = Solver.DG(Params,physics,mesh)
solver.solve()


### Postprocess
# Error
solver.time = 0.
TotErr,_ = Post.get_error(mesh, physics, solver, "Scalar")
# Plot
axis = None
# axis = [-5., 5., -5., 5.]
Plot.prepare_plot(axis=axis, linewidth=0.5)
Plot.PlotSolution(mesh, physics, solver, "Scalar", Equidistant=True, PlotExact=False, include_mesh=True, 
	Regular2D=True, show_triangulation=False)
Plot.save_figure(file_name=CurrentDir+'Gaussian', file_type='pdf', crop_level=2)
Plot.plot_line_probe(mesh, physics, solver, "Scalar", xy1=[-5.,-5.], xy2=[5.,5.], nPoint=101, PlotExact=True, PlotIC=True)
# Post.get_boundary_info(mesh, physics, solver, "y1", "Scalar", integrate=True, 
# 		vec=[0.,1.], dot_normal_with_vec=True, plot_vs_x=True, plot_vs_y=False)
Plot.show_plot()

# U = physics.U.Arrays[0]
# code.interact(local=locals())
