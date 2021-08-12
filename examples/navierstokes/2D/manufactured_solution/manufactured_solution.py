TimeStepping = {
	"FinalTime" : 0.5,
	"NumTimeSteps" : 10,
	"TimeStepper" : "SSPRK3",
}

Numerics = {
	"Solver" : "DG",
	"SolutionOrder" : 1,
	"SolutionBasis" : "LagrangeQuad",
	"DiffFluxSwitch" : True,
}

num_elem_x = 1
num_elem_y = 1
Mesh = {
	"ElementShape" : "Quadrilateral",
	"NumElemsX" : num_elem_x,
	"NumElemsY" : num_elem_y,
	"xmin" : 0.,
	"xmax" : 10.,
	"ymin" : 0.,
	"ymax" : 10.,
	"PeriodicBoundariesX" : ["x2", "x1"],
	"PeriodicBoundariesY" : ["y1", "y2"],
}

Physics = {
	"Type" : "NavierStokes",
	"ConvFluxNumerical" : "Roe",
	"DiffFluxNumerical" : "SIP",
}

InitialCondition = {
	"Function" : "ManufacturedSolution",
}

ExactSolution = InitialCondition.copy()

SourceTerms = {
	"Source1" : { # Name of source term ("Source1") doesn't matter
		"Function" : "ManufacturedSource",
	},
}

Output = {
	"AutoPostProcess" : True,
}
