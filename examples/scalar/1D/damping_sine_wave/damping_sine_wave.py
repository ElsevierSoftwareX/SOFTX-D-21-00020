import numpy as np

TimeStepping = {
    "InitialTime" : 0.,
    "FinalTime" : 0.5,
    "num_time_steps" : 40,
    "TimeScheme" : "RK4",
}

Numerics = {
    "InterpOrder" : 2,
    "InterpBasis" : "LegendreSeg",
    "Solver" : "DG",
}

Output = {
    "AutoPostProcess" : True
}

Mesh = {
    "File" : None,
    "ElementShape" : "Segment",
    "NumElemsX" : 16,
    "NumElemsY" : 2,
    "xmin" : -1.,
    "xmax" : 1.,
    # "PeriodicBoundariesX" : ["x1", "x2"],
}

Physics = {
    "Type" : "ConstAdvScalar",
    "ConvFluxNumerical" : "LaxFriedrichs",
    "ConstVelocity" : 1.,
}

nu = -3.
InitialCondition = {
    "Function" : "DampingSine",
    "omega" : 2*np.pi,
    "nu" : nu,
}

ExactSolution = InitialCondition.copy()

BoundaryConditions = {
    "x1" : {
	    "Function" : "DampingSine",
	    "omega" : 2*np.pi,
	    "nu" : nu,
    	"BCType" : "StateAll",
    },
    "x2" : {
    	#"Function" : None,
    	"BCType" : "Extrapolate",
    },
}

SourceTerms = {
	"source1" : {
		"Function" : "SimpleSource",
		"nu" : nu,
	},
}
