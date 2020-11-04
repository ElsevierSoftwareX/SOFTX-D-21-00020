# ------------------------------------------------------------------------ #
#
#       File : src/numerics/quadrature/quadrilateral.py
#
#       Contains functions to evaluate quadrature for quadrilateral shapes
#      
# ------------------------------------------------------------------------ #
import numpy as np
import numerics.quadrature.segment as qseg


def get_quadrature_points_weights(order, quad_type, num_pts_colocated=0):
    '''
    Calls the segment quadrature function to obtain quadrature points and 
    restructures them for quadrilateral shapes using tensor products

    Inputs:
    ------- 
        order: solution order
        quad_type: Enum that points to the appropriate quadrature calc
        num_pts_colocated: if greater than 0, then a colocated scheme will
            be used, i.e. the quadrature points will be the same as the 
            solution nodes; this value then determines the number of 
            quadrature points

    Outputs:
    --------
        qpts: quadrature point coordinates [nq, ndims]
        qwts: quadrature weights [nq, 1]
    '''
    # Get quadrature points and weights for segment		
    qpts_seg, qwts_seg = qseg.get_quadrature_points_weights(order, quad_type, 
            int(np.sqrt(num_pts_colocated)))

    # Weights
    qwts = np.reshape(np.outer(qwts_seg, qwts_seg), (-1,), 'F').reshape(-1, 1)
    # Points
    qpts = np.zeros([qwts.shape[0], 2])
    qpts[:, 0] = np.tile(qpts_seg, (qpts_seg.shape[0], 1)).reshape(-1)
    qpts[:, 1] = np.repeat(qpts_seg, qpts_seg.shape[0], axis=0).reshape(-1)

    return qpts, qwts