import code
from enum import Enum, auto
import numpy as np
from scipy.optimize import fsolve, root

from physics.base.data import FcnBase, BCWeakRiemann, BCWeakPrescribed, SourceBase, ConvNumFluxBase


class FcnType(Enum):
    SmoothIsentropicFlow = auto()
    MovingShock = auto()
    IsentropicVortex = auto()
    DensityWave = auto()
    RiemannProblem = auto()
    SmoothRiemannProblem = auto()
    TaylorGreenVortex = auto()
    ExactRiemannSolution = auto()

class BCType(Enum):
	SlipWall = auto()
	PressureOutlet = auto()


class SourceType(Enum):
    StiffFriction = auto()
    TaylorGreenSource = auto()


class ConvNumFluxType(Enum):
	Roe = auto()


'''
State functions
'''

class SmoothIsentropicFlow(FcnBase):
	def __init__(self, a=0.9):
		self.a = a

	def get_state(self, physics, x, t):
		
		a = self.a
		gamma = physics.gamma
		irho, irhou, irhoE = physics.GetStateIndices()
	
		# Up = np.zeros([x.shape[0], physics.NUM_STATE_VARS])

		rho0 = lambda x, a: 1. + a*np.sin(np.pi*x)
		pressure = lambda rho, gamma: rho**gamma
		rho = lambda x1, x2, a: 0.5*(rho0(x1, a) + rho0(x2, a))
		vel = lambda x1, x2, a: np.sqrt(3)*(rho(x1, x2, a) - rho0(x1, a))

		f1 = lambda x1, x, t, a: x + np.sqrt(3)*rho0(x1, a)*t - x1
		f2 = lambda x2, x, t, a: x - np.sqrt(3)*rho0(x2, a)*t - x2

		xr = x.reshape(-1)

		Up = np.zeros([x.shape[0], physics.NUM_STATE_VARS])

		x1 = fsolve(f1, 0.*xr, (xr, t, a))
		if np.abs(x1.any()) > 1.: raise Exception("x1 = %g out of range" % (x1))
		x2 = fsolve(f2, 0.*xr, (xr, t, a))
		if np.abs(x2.any()) > 1.: raise Exception("x2 = %g out of range" % (x2))
			
		den = rho(x1, x2, a)
		u = vel(x1, x2, a)
		p = pressure(den, gamma)
		rhoE = p/(gamma - 1.) + 0.5*den*u*u

		Up[:, irho] = den
		Up[:, irhou] = den*u
		Up[:, irhoE] = rhoE

		return Up


class MovingShock(FcnBase):
	def __init__(self, M = 5.0, xshock = 0.2):
		self.M = M
		self.xshock = xshock

	def get_state(self, physics, x, t):

		M = self.M
		xshock = self.xshock

		srho, srhou, srhoE = physics.get_state_slices()

		gamma = physics.gamma
		
		Up = np.zeros([x.shape[0], physics.NUM_STATE_VARS])
		''' Pre-shock state '''
		rho1 = 1.
		p1 = 1.e5
		u1 = 0.

		''' Update xshock based on shock speed '''
		a1 = np.sqrt(gamma*p1/rho1)
		W = M*a1 
		us = u1 + W # shock speed in lab frame
		xshock = xshock + us*t

		''' Post-shock state '''
		rho2 = (gamma + 1.)*M**2./((gamma - 1.)*M**2. + 2.)*rho1
		p2 = (2.*gamma*M**2. - (gamma - 1.))/(gamma + 1.)*p1
		# To get velocity, first work in reference frame fixed to shock
		ux = W
		uy = ux*rho1/rho2
		# Convert back to lab frame
		u2 = W + u1 - uy

		''' Fill state '''
		ileft = (x <= xshock).reshape(-1)
		iright = (x > xshock).reshape(-1)

		# Density
		Up[iright, srho] = rho1
		Up[ileft, srho] = rho2
		# Momentum
		Up[iright, srhou] = rho1*u1
		Up[ileft, srhou] = rho2*u2
		# Energy
		Up[iright, srhoE] = p1/(gamma - 1.) + 0.5*rho1*u1*u1
		Up[ileft, srhoE] = p2/(gamma - 1.) + 0.5*rho2*u2*u2

		return Up


class IsentropicVortex(FcnBase):
	def __init__(self, rhob=1., ub=1., vb=1., pb=1., vs=5.):
		self.rhob = rhob
		self.ub = ub
		self.vb = vb
		self.pb = pb
		self.vs = vs

	def get_state(self, physics, x, t):		
		Up = np.zeros([x.shape[0], physics.NUM_STATE_VARS])
		gamma = physics.gamma
		Rg = physics.R

		### Parameters
		# Base flow
		rhob = self.rhob
		# x-velocity
		ub = self.ub
		# y-velocity
		vb = self.vb
		# pressure
		pb = self.pb
		# vortex strength
		vs = self.vs
		# Make sure Rg is 1
		if Rg != 1.:
			raise ValueError

		# Base temperature
		Tb = pb/(rhob*Rg)

		# Entropy
		s = pb/rhob**gamma

		xr = x[:,0] - ub*t
		yr = x[:,1] - vb*t
		r = np.sqrt(xr**2. + yr**2.)

		# Perturbations
		dU = vs/(2.*np.pi)*np.exp(0.5*(1-r**2.))
		du = dU*-yr
		dv = dU*xr

		dT = -(gamma - 1.)*vs**2./(8.*gamma*np.pi**2.)*np.exp(1. - r**2.)

		u = ub + du 
		v = vb + dv 
		T = Tb + dT

		# Convert to conservative variables
		rho = np.power(T/s, 1./(gamma - 1.))
		rhou = rho*u
		rhov = rho*v
		rhoE = rho*Rg/(gamma - 1.)*T + 0.5*(rhou*rhou + rhov*rhov)/rho

		Up[:, 0] = rho
		Up[:, 1] = rhou
		Up[:, 2] = rhov
		Up[:, 3] = rhoE

		return Up


class DensityWave(FcnBase):
	def __init__(self, p=1.0):
		self.p = p

	def get_state(self, physics, x, t):
		p = self.p
		srho, srhou, srhoE = physics.get_state_slices()
		gamma = physics.gamma

		Up = np.zeros([x.shape[0], physics.NUM_STATE_VARS])
		
		rho = 1.0 + 0.1*np.sin(2.*np.pi*x)
		rhou = rho*1.0
		rhoE = (p/(gamma - 1.)) + 0.5*rhou**2/rho

		Up[:,srho] = rho
		Up[:,srhou] = rhou
		Up[:,srhoE] = rhoE

		return Up


class RiemannProblem(FcnBase):
	def __init__(self, uL=np.array([1.,0.,1.]), uR=np.array([0.125,0.,0.1]), xshock=0.):
		# Default conditions set up for Sod Problem.
		self.uL = uL
		self.uR = uR
		self.xshock = xshock

	def get_state(self, physics, x, t):

		xshock = self.xshock
		uL = self.uL
		uR = self.uR

		rhoL = uL[0]
		vL = uL[1]
		pL = uL[2]
		
		rhoR = uR[0]
		vR = uR[1]
		pR = uR[2]

		srho, srhou, srhoE = physics.get_state_slices()

		gam = physics.gamma
		
		Up = np.zeros([x.shape[0], physics.NUM_STATE_VARS])

		''' Fill state '''
		ileft = (x <= xshock).reshape(-1)
		iright = (x > xshock).reshape(-1)

		# Density
		Up[iright, srho] = rhoR
		Up[ileft, srho] = rhoL
		# Momentum
		Up[iright, srhou] = rhoR*vR
		Up[ileft, srhou] = rhoL*vL
		# Energy
		Up[iright, srhoE] = pR/(gam-1.) + 0.5*rhoR*vR*vR
		Up[ileft, srhoE] = pL/(gam-1.) + 0.5*rhoL*vL*vL

		return Up

class ExactRiemannSolution(FcnBase):
	# This is only used for exact solutions. Not for IC or BCs
	def __init__(self, uL=np.array([1.,0.,1.]), uR=np.array([0.125,0.,0.1]), xmin=0., xmax=1., xshock=0.5):
		self.uL = uL
		self.uR = uR
		self.xmin = xmin
		self.xmax = xmax
		self.xshock = xshock

	def get_state(self, physics, x, t):

		uL = self.uL
		uR = self.uR
		L = self.xmax - self.xmin
		xshock = self.xshock
		Up = np.zeros([x.shape[0], physics.NUM_STATE_VARS])
		gam = physics.gamma
		srho, srhou, srhoE = physics.get_state_slices()

		rho4 = uL[0]; p4 = uL[2]; u4 = uL[1];
		rho1 = uR[0]; p1 = uR[2]; u1 = uR[1];

		c4 = np.sqrt(gam*p4/rho4)
		c1 = np.sqrt(gam*p1/rho1)
		p41 = p4/p1

		def F(y):
			F = y*(1.+(gam-1.)/(2.*c4)*(u4-u1-c1/gam*(y-1.)/np.sqrt((gam+1.)/(2.*gam)*(y-1.)+1)))**(-2.*gam/(gam-1))-p4/p1;
			return F			

		y0 = 0.5*p4/p1
		Y = fsolve(F,y0)

		# can now get p2
		p2 = Y*p1

		# Equation 11
		u2 = u1 + c1/gam*(p2/p1-1)/np.sqrt((gam+1)/(2*gam)*(p2/p1-1) + 1)
		# Equation 10
		num = (gam+1)/(gam-1) + p2/p1
		den = 1 + (gam+1)/(gam-1)*(p2/p1)
		c2 = c1*np.sqrt(p2/p1*num/den)
		# Equation 12 - shock speed
		V = u1 + c1*np.sqrt((gam+1)/(2*gam)*(p2/p1-1) + 1)
		# density for state 2
		rho2 = gam*p2/c2**2

		# Equations 13 and 14
		u3 = u2
		p3 = p2 
		# Equation 16
		c3 = (gam-1)/2*(u4-u3+2/(gam-1)*c4)
		rho3 = gam*p3/c3**2

		# now deal with expansion fan
		xe1 = (u4-c4)*t + xshock; # "start" of expansion fan
		xe2 = (t*((gam+1)/2*u3 - (gam-1)/2*u4 - c4)+xshock) # end

		# code.interact(local=locals())
		# xe = np.linspace(xe1,xe2,101);
		# ue = 2/(gam+1)*(xe/t + (gam-1)/2*u4 + c4)
		# ce = ue - xe/t
		# pe = p4*(ce/c4)**(2*gam/(gam-1))
		# rhoe = gam*pe/ce**2		

		# # create x's for different regions
		# dx = xe[2]-xe[1]
		# x4 = np.arange(xe1, -L, -dx)
		# x4 = x4[::-1]

		# location of shock
		xs = V*t + xshock
		# location of contact
		xc = u2*t + xshock

		uu = np.zeros_like(x); pp = np.zeros_like(x); rr = np.zeros_like(x);

		for i in range(len(x)):
		    if x[i] <= xe1:
		        uu[i] = u4; pp[i] = p4; rr[i] = rho4;
		    elif x[i] > xe1 and x[i] <= xe2:
		        uu[i] = (2/(gam+1)*((x[i]-xshock)/t + (gam-1)/2*u4 + c4)) 
		        cc = uu[i] - (x[i]-xshock)/t
		        pp[i] = p4*(cc/c4)**(2*gam/(gam-1))
		        rr[i] = gam*pp[i]/cc**2
		    elif x[i] > xe2 and x[i] <= xc:
		        uu[i] = u3; pp[i] = p3; rr[i] = rho3;
		    elif x[i] > xc and x[i] <= xs:
		        uu[i] = u2; pp[i] = p2; rr[i] = rho2;
		    else:
		        uu[i] = u1; pp[i] = p1; rr[i] = rho1;

		Up[:, srho] = rr
		Up[:, srhou] = rr*uu
		Up[:, srhoE] = pp/(gam-1.) + 0.5*rr*uu*uu

		return Up

class SmoothRiemannProblem(FcnBase):
	def __init__(self, uL=np.array([1.,0.,1.]), uR=np.array([0.125,0.,0.1]), w=0.05, xshock=0.):
		# Default conditions set up for Sod Problem.
		self.uL = uL
		self.uR = uR
		self.w = w
		self.xshock = xshock

	def get_state(self, physics, x, t):

		xshock = self.xshock
		uL = self.uL
		uR = self.uR
		w = self.w

		rhoL = uL[0]
		vL = uL[1]
		pL = uL[2]
		
		rhoR = uR[0]
		vR = uR[1]
		pR = uR[2]

		srho, srhou, srhoE = physics.get_state_slices()

		gam = physics.gamma
		
		Up = np.zeros([x.shape[0], physics.NUM_STATE_VARS])

		# w = 0.05
		def set_tanh(a,b,w,xo):
			return 0.5*((a+b)+(b-a)*np.tanh((x-xo)/w))
		# Density
		Up[:, srho] =  set_tanh(rhoL,rhoR,w,xshock)

		# Momentum
		Up[:, srhou] = set_tanh(rhoL*vL,rhoR*vR,w,xshock)
		# Energy
		rhoeL = pL/(gam-1.) + 0.5*rhoL*vL*vL
		rhoeR = pR/(gam-1.) + 0.5*rhoR*vR*vR
		Up[:, srhoE] = set_tanh(rhoeL,rhoeR,w,xshock)

		return Up


class TaylorGreenVortex(FcnBase):

	def get_state(self, physics, x, t):		
		Up = np.zeros([x.shape[0], physics.NUM_STATE_VARS])
		gamma = physics.gamma
		Rg = physics.R

		irho, irhou, irhov, irhoE = physics.GetStateIndices()

		rho = 1.
		u = np.sin(np.pi*x[:, 0])*np.cos(np.pi*x[:, 1])
		v = -np.cos(np.pi*x[:, 0])*np.sin(np.pi*x[:, 1])
		p = 0.25*(np.cos(2.*np.pi*x[:, 0]) + np.cos(2*np.pi*x[:, 1])) + 1.
		E = p/(rho*(gamma - 1.)) + 0.5*(u**2. + v**2.)

		Up[:, irho] = rho
		Up[:, irhou] = rho*u
		Up[:, irhov] = rho*v
		Up[:, irhoE] = rho*E

		return Up


'''
Boundary conditions
'''

class SlipWall(BCWeakPrescribed):
	def get_boundary_state(self, physics, x, t, normals, UpI):
		smom = physics.GetMomentumSlice()

		n_hat = normals/np.linalg.norm(normals, axis=1, keepdims=True)

		rhoveln = np.sum(UpI[:, smom] * n_hat, axis=1, keepdims=True)
		UpB = UpI.copy()
		UpB[:, smom] -= rhoveln * n_hat

		return UpB


class PressureOutlet(BCWeakPrescribed):
	def __init__(self, p):
		self.p = p

	def get_boundary_state(self, physics, x, t, normals, UpI):
		srho = physics.get_state_slice("Density")
		srhoE = physics.get_state_slice("Energy")
		smom = physics.GetMomentumSlice()

		UpB = UpI.copy()

		n_hat = normals/np.linalg.norm(normals, axis=1, keepdims=True)

		# Pressure
		pB = self.p

		gamma = physics.gamma

		# gam = physics.gamma
		# igam = 1./gam
		# gmi = gam - 1.
		# igmi = 1./gmi

		# Interior velocity in normal direction
		rhoI = UpI[:, srho]
		velI = UpI[:, smom]/rhoI
		velnI = np.sum(velI*n_hat, axis=1, keepdims=True)

		if np.any(velnI < 0.):
			print("Incoming flow at outlet")

		# Compute interior pressure
		# rVI2 = np.sum(UpI[:,imom]**2., axis=1, keepdims=True)/rhoI
		# pI = gmi*(UpI[:,irhoE:irhoE+1] - 0.5*rVI2)
		pI = physics.ComputeScalars("Pressure", UpI)

		if np.any(pI < 0.):
			raise errors.NotPhysicalError

		# Interior speed of sound
		# cI = np.sqrt(gam*pI/rhoI)
		cI = physics.ComputeScalars("SoundSpeed", UpI)
		JI = velnI + 2.*cI/(gamma - 1.)
		veltI = velI - velnI*n_hat

		# Normal Mach number
		Mn = velnI/cI
		if np.any(Mn >= 1.):
			return UpB

		# Boundary density from interior entropy
		rhoB = rhoI*np.power(pB/pI, 1./gamma)
		UpB[:, srho] = rhoB

		# Exterior speed of sound
		cB = np.sqrt(gamma*pB/rhoB)
		velB = (JI - 2.*cB/(gamma-1.))*n_hat + veltI
		UpB[:, smom] = rhoB*velB
		# dVn = 2.*igmi*(cI-cB)
		# UpB[:,imom] = rhoB*dVn*n_hat + rhoB*UpI[:,imom]/rhoI

		# Exterior energy
		# rVB2 = np.sum(UpB[:,imom]**2., axis=1, keepdims=True)/rhoB
		rhovel2B = rhoB*np.sum(velB**2., axis=1, keepdims=True)
		UpB[:, srhoE] = pB/(gamma - 1.) + 0.5*rhovel2B

		return UpB


'''
Source term functions
'''

class StiffFriction(SourceBase):
	def __init__(self, nu=-1):
		self.nu = nu

	def get_source(self, physics, FcnData, x, t):
		nu = self.nu
		# irho = physics.GetStateIndex("Density")
		# irhou = physics.GetStateIndex("XMomentum")
		# irhoE = physics.GetStateIndex("Energy")

		irho, irhou, irhoE = physics.GetStateIndices()
		
		U = FcnData.U
		
		S = np.zeros_like(U)

		eps = 1.0e-12
		S[:, irho] = 0.0
		S[:, irhou] = nu*(U[:, irhou])
		S[:, irhoE] = nu*((U[:, irhou])**2/(eps+U[:, irho]))
		
		return S

	# def get_jacobian(self, physics, FcnData, x, t):

	# 	nu = self.nu

	# 	U = FcnData.U
	# 	irho, irhou, irhoE = physics.GetStateIndices()

	# 	jac = np.zeros([U.shape[0], U.shape[-1], U.shape[-1]])
	# 	vel = U[:, 1]/(1.0e-12 + U[:, 0])

	# 	jac[:, irhou, irhou] = nu
	# 	jac[:, irhoE, irho] = -nu*vel**2
	# 	jac[:, irhoE, irhou] = 2.0*nu*vel
	# 	# jac[:, 1,1] = nu
	# 	# jac[:, 2, 0] = -nu*vel**2
	# 	# jac[:, 2, 1] = 2.0*nu*vel

	# 	return jac
	def get_jacobian(self, physics, FcnData, x, t):

		nu = self.nu
		U = FcnData.U

		irho, irhou, irhoE = physics.GetStateIndices()

		jac = np.zeros([U.shape[0], U.shape[-1], U.shape[-1]])
		vel = U[:, 1]/(1.0e-12 + U[:, 0])

		jac[:, irhou, irhou] = nu
		jac[:, irhoE, irho] = -nu*vel**2
		jac[:, irhoE, irhou] = 2.0*nu*vel
		# jac[:, 1, 1] = nu
		# jac[:, 2, 0] = -nu*vel**2
		# jac[:, 2, 1] = 2.0*nu*vel

		return jac


class TaylorGreenSource(SourceBase):

	def get_source(self, physics, FcnData, x, t):
		gamma = physics.gamma

		irho, irhou, irhov, irhoE = physics.GetStateIndices()
		
		U = FcnData.U
		
		S = np.zeros_like(U)

		S[:, irhoE] = np.pi/(4.*(gamma - 1.))*(np.cos(3.*np.pi*x[:, 0])*np.cos(np.pi*x[:, 1]) - 
				np.cos(np.pi*x[:, 0])*np.cos(3.*np.pi*x[:, 1]))
		
		return S


'''
Numerical flux functions
'''

class Roe1D(ConvNumFluxBase):
	def __init__(self, Up=None):
		if Up is not None:
			n = Up.shape[0]
			ns = Up.shape[1]
			dim = ns - 2
		else:
			n = 0; ns = 0; dim = 0

		# self.velL = np.zeros([n,dim])
		# self.velR = np.zeros([n,dim])
		self.UL = np.zeros_like(Up)
		self.UR = np.zeros_like(Up)
		self.vel = np.zeros([n, dim])
		# self.rhoL_sqrt = np.zeros([n,1])
		# self.rhoR_sqrt = np.zeros([n,1])
		# self.HL = np.zeros([n,1])
		# self.HR = np.zeros([n,1])
		# self.rhoRoe = np.zeros([n,1])
		# self.velRoe = np.zeros([n,dim])
		# self.HRoe = np.zeros([n,1])
		# self.c2 = np.zeros([n,1])
		# self.c = np.zeros([n,1])
		# self.dvel = np.zeros([n,dim])
		# self.drho = np.zeros([n,1])
		# self.dp = np.zeros([n,1])
		self.alphas = np.zeros_like(Up)
		self.evals = np.zeros_like(Up)
		self.R = np.zeros([n, ns, ns])
		# self.FRoe = np.zeros_like(u)
		# self.FL = np.zeros_like(u)
		# self.FR = np.zeros_like(u)

	# def AllocHelperArrays(self, u):
	# 	self.__init__(u)

	def RotateCoordSys(self, imom, U, n):
		U[:,imom] *= n

		return U

	def UndoRotateCoordSys(self, imom, U, n):
		U[:,imom] /= n

		return U

	def RoeAverageState(self, EqnSet, srho, velL, velR, uL, uR):
		# rhoL_sqrt = self.rhoL_sqrt
		# rhoR_sqrt = self.rhoR_sqrt
		# HL = self.HL 
		# HR = self.HR 

		rhoL_sqrt = np.sqrt(uL[:,srho])
		rhoR_sqrt = np.sqrt(uR[:,srho])
		HL = EqnSet.ComputeScalars("TotalEnthalpy", uL, flag_non_physical=True)
		HR = EqnSet.ComputeScalars("TotalEnthalpy", uR, flag_non_physical=True)

		# self.velRoe = (rhoL_sqrt*velL + rhoR_sqrt*velR)/(rhoL_sqrt+rhoR_sqrt)
		# self.HRoe = (rhoL_sqrt*HL + rhoR_sqrt*HR)/(rhoL_sqrt+rhoR_sqrt)
		# self.rhoRoe = rhoL_sqrt*rhoR_sqrt

		velRoe = (rhoL_sqrt*velL + rhoR_sqrt*velR)/(rhoL_sqrt+rhoR_sqrt)
		HRoe = (rhoL_sqrt*HL + rhoR_sqrt*HR)/(rhoL_sqrt+rhoR_sqrt)
		rhoRoe = rhoL_sqrt*rhoR_sqrt

		return rhoRoe, velRoe, HRoe

	def GetDifferences(self, EqnSet, srho, velL, velR, uL, uR):
		# dvel = self.dvel
		# drho = self.drho
		# dp = self.dp 

		dvel = velR - velL
		drho = uR[:,srho] - uL[:,srho]
		dp = EqnSet.ComputeScalars("Pressure", uR) - \
			EqnSet.ComputeScalars("Pressure", uL)

		return dvel, drho, dp

	def GetAlphas(self, c, c2, dp, dvel, drho, rhoRoe):
		alphas = self.alphas 

		alphas[:,0:1] = 0.5/c2*(dp - c*rhoRoe*dvel[:,0:1])
		alphas[:,1:2] = drho - dp/c2 
		alphas[:,-1:] = 0.5/c2*(dp + c*rhoRoe*dvel[:,0:1])

		return alphas 

	def GetEigenvalues(self, velRoe, c):
		evals = self.evals 

		evals[:,0:1] = velRoe[:,0:1] - c
		evals[:,1:2] = velRoe[:,0:1]
		evals[:,-1:] = velRoe[:,0:1] + c
		
		return evals 

	def GetRightEigenvectors(self, c, evals, velRoe, HRoe):
		R = self.R

		# first row
		# R[:,0,[0,1,-1]] = 1.
		R[:,0,0:2] = 1.; R[:,0,-1] = 1.
		# second row
		R[:,1,0] = evals[:,0]; R[:,1,1] = velRoe[:,0]; R[:,1,-1] = evals[:,-1]
		# last row
		R[:,-1,0:1] = HRoe - velRoe[:,0:1]*c; R[:,-1,1:2] = 0.5*np.sum(velRoe*velRoe, axis=1, keepdims=True)
		R[:,-1,-1:] = HRoe + velRoe[:,0:1]*c

		return R 


	def compute_flux(self, EqnSet, UL_std, UR_std, n):
		'''
		Function: ConvFluxLaxFriedrichs
		-------------------
		This function computes the numerical flux (dotted with the normal)
		using the Lax-Friedrichs flux function

		INPUTS:
		    gam: specific heat ratio
		    UL: Left state
		    UR: Right state
		    n: Normal vector (assumed left to right)

		OUTPUTS:
		    F: Numerical flux dotted with the normal, i.e. F_hat dot n
		'''

		# Extract helper arrays
		UL = self.UL 
		UR = self.UR
		# velL = self.velL
		# velR = self.velR 
		# c2 = self.c2
		# c = self.c 
		# alphas = self.alphas 
		# evals = self.evals 
		# R = self.R 
		# FRoe = self.FRoe 
		# FL = self.FL 
		# FR = self.FR 

		# Indices
		srho = EqnSet.get_state_slice("Density")
		smom = EqnSet.GetMomentumSlice()

		gamma = EqnSet.gamma

		NN = np.linalg.norm(n, axis=1, keepdims=True)
		n1 = n/NN

		# Copy values before rotating
		UL[:] = UL_std
		UR[:] = UR_std

		# Rotated coordinate system
		UL = self.RotateCoordSys(smom, UL, n1)
		UR = self.RotateCoordSys(smom, UR, n1)

		# Velocities
		velL = UL[:, smom]/UL[:, srho]
		velR = UR[:, smom]/UR[:, srho]

		rhoRoe, velRoe, HRoe = self.RoeAverageState(EqnSet, srho, velL, velR, UL, UR)

		# Speed of sound from Roe-averaged state
		c2 = (gamma - 1.)*(HRoe - 0.5*np.sum(velRoe*velRoe, axis=1, keepdims=True))
		c = np.sqrt(c2)

		# differences
		dvel, drho, dp = self.GetDifferences(EqnSet, srho, velL, velR, UL, UR)

		# alphas (left eigenvectors multipled by dU)
		# alphas[:,[0]] = 0.5/c2*(dp - c*rhoRoe*dvel[:,[0]])
		# alphas[:,[1]] = drho - dp/c2 
		# alphas[:,ydim] = rhoRoe*dvel[:,[-1]]
		# alphas[:,[-1]] = 0.5/c2*(dp + c*rhoRoe*dvel[:,[0]])
		alphas = self.GetAlphas(c, c2, dp, dvel, drho, rhoRoe)

		# Eigenvalues
		# evals[:,[0]] = velRoe[:,[0]] - c
		# evals[:,1:-1] = velRoe[:,[0]]
		# evals[:,[-1]] = velRoe[:,[0]] + c
		evals = self.GetEigenvalues(velRoe, c)

		# Right eigenvector matrix
		# first row
		# R[:,0,[0,1,-1]] = 1.; R[:,0,ydim] = 0.
		# # second row
		# R[:,1,0] = evals[:,0]; R[:,1,1] = velRoe[:,0]; R[:,1,ydim] = 0.; R[:,1,-1] = evals[:,-1]
		# # last row
		# R[:,-1,[0]] = HRoe - velRoe[:,[0]]*c; R[:,-1,[1]] = 0.5*np.sum(velRoe*velRoe, axis=1, keepdims=True)
		# R[:,-1,[-1]] = HRoe + velRoe[:,[0]]*c; R[:,-1,ydim] = velRoe[:,[-1]]
		# # [third] row
		# R[:,ydim,0] = velRoe[:,[-1]];  R[:,ydim,1] = velRoe[:,[-1]]; 
		# R[:,ydim,-1] = velRoe[:,[-1]]; R[:,ydim,ydim] = 1.
		R = self.GetRightEigenvectors(c, evals, velRoe, HRoe)

		# Form flux Jacobian matrix multiplied by dU
		FRoe = np.matmul(R, np.expand_dims(np.abs(evals)*alphas, axis=2)).squeeze(axis=2)

		FRoe = self.UndoRotateCoordSys(smom, FRoe, n1)

		# Left flux
		FL = EqnSet.ConvFluxProjected(UL_std, n1)

		# Right flux
		FR = EqnSet.ConvFluxProjected(UR_std, n1)
		
		return NN*(0.5*(FL+FR) - 0.5*FRoe)


class Roe2D(Roe1D):

	def RotateCoordSys(self, imom, U, n):
		vel = self.vel
		vel[:] = U[:,imom]

		vel[:,0] = np.sum(U[:,imom]*n, axis=1)
		vel[:,1] = np.sum(U[:,imom]*n[:,::-1]*np.array([[-1.,1.]]), axis=1)
		
		U[:,imom] = vel

		return U

	def UndoRotateCoordSys(self, imom, U, n):
		vel = self.vel
		vel[:] = U[:,imom]

		vel[:,0] = np.sum(U[:,imom]*n*np.array([[1.,-1.]]), axis=1)
		vel[:,1] = np.sum(U[:,imom]*n[:,::-1], axis=1)

		U[:,imom] = vel

		return U

	def GetAlphas(self, c, c2, dp, dvel, drho, rhoRoe):
		alphas = self.alphas 

		alphas = super().GetAlphas(c, c2, dp, dvel, drho, rhoRoe)

		alphas[:,2:3] = rhoRoe*dvel[:,-1:]

		return alphas 

	def GetEigenvalues(self, velRoe, c):
		evals = self.evals 

		evals = super().GetEigenvalues(velRoe, c)

		evals[:,2:3] = velRoe[:,0:1]

		return evals 

	def GetRightEigenvectors(self, c, evals, velRoe, HRoe):
		R = self.R

		R = super().GetRightEigenvectors(c, evals, velRoe, HRoe)

		i = 2

		# first row
		R[:,0,i] = 0.
		# second row
		R[:,1,i] = 0.
		# last row
		R[:,-1,i] = velRoe[:,-1]
		# [third] row
		R[:,i,0] = velRoe[:,-1];  R[:,i,1] = velRoe[:,-1]; 
		R[:,i,-1] = velRoe[:,-1]; R[:,i,i] = 1.

		return R 



