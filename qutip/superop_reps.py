# -*- coding: utf-8 -*-
"""
Created on Thu May 23 16:35:42 2013

@author: dcriger
"""

from operator import add

from numpy.core.multiarray import array
from numpy.core.shape_base import hstack
from numpy.matrixlib.defmatrix import matrix
from numpy import sqrt
from scipy.linalg import eig

from qutip.superoperator import vec2mat, spre, spost
from qutip.qobj import Qobj

def _dep_super(pe):
    """
    Returns the superoperator corresponding to qubit depolarization for a
    given parameter pe.

    # TODO if this is going into production (hopefully it isn't) then check
    CPTP, expand to arbitrary dimensional systems, etc.
    """
    return Qobj(dims=[[2, 2], [2, 2]],
                inpt=array([[1. - pe / 2., 0., 0., pe / 2.],
                            [0., 1. - pe, 0., 0.],
                            [0., 0., 1. - pe, 0.],
                            [pe / 2., 0., 0., 1. - pe / 2.]]))


def _dep_choi(pe):
    """
    Returns the choi matrix corresponding to qubit depolarization for a
    given parameter pe.

    # TODO if this is going into production (hopefully it isn't) then check
    CPTP, expand to arbitrary dimensional systems, etc.
    """
    return Qobj(dims=[[2, 2], [2, 2]],
                inpt=array([[1. - pe / 2., 0., 0., 1. - pe],
                            [0., pe / 2., 0., 0.],
                            [0., 0., pe / 2., 0.],
                            [1. - pe, 0., 0., 1. - pe / 2.]]))


#- PRIVATE CONVERSION FUNCTIONS -----------------------------------------------
# These functions handle the main work of converting between representations,
# and are exposed below by other functions that add postconditions about types.
#
# TODO: handle type='kraus' as a three-index Qobj, rather than as a list?

def _super_tofrom_choi(q_oper):
    """
    We exploit that the basis transformation between Choi and supermatrix
    representations squares to the identity, so that if we munge Qobj.type,
    we can use the same function.
    
    Since this function doesn't respect :attr:`Qobj.type`, we mark it as
    private; only those functions which wrap this in a way so as to preserve
    type should be called externally.
    """
    data = q_oper.data.toarray()
    sqrt_shape = sqrt(data.shape[0])
    return Qobj(dims=q_oper.dims,
                inpt=data.reshape([sqrt_shape] * 4).
                transpose(3, 1, 2, 0).reshape(q_oper.data.shape))

def super_to_choi(q_oper):
    # TODO: deprecate and make private in favor of to_choi,
    #       which looks at Qobj.type to determine the right conversion function.
    """
    Takes a superoperator to a Choi matrix
    # TODO Sanitize input, incorporate as method on Qobj if type=='super'
    """
    q_oper = _super_tofrom_choi(q_oper)
    q_oper.superrep = 'choi'
    return q_oper

def choi_to_super(q_oper):
    # TODO: deprecate and make private in favor of to_super,
    #       which looks at Qobj.type to determine the right conversion function.
    """
    Takes a Choi matrix to a superoperator
    # TODO Sanitize input, Abstract-ify application of channels to states
    """
    q_oper = super_to_choi(q_oper)
    q_oper.superrep = 'super'
    return q_oper

def choi_to_kraus(q_oper):
    """
    Takes a Choi matrix and returns a list of Kraus operators.
    # TODO Create a new class structure for quantum channels, perhaps as a
    strict sub-class of Qobj.
    """
    vals, vecs = eig(q_oper.data.todense())
    vecs = list(map(array, zip(*vecs)))
    return list(map(lambda x: Qobj(inpt=x),
                    [sqrt(vals[j]) * vec2mat(vecs[j])
                     for j in range(len(vals))]))

def kraus_to_choi(kraus_list):
    """
    Takes a list of Kraus operators and returns the Choi matrix for the channel
    represented by the Kraus operators in `kraus_list`
    """
    kraus_mat_list = list(map(lambda x: matrix(x.data.todense()), kraus_list))
    op_len = len(kraus_mat_list[0])
    op_rng = range(op_len)
    choi_blocks = array([[sum([op[:, c_ix] * array([op.H[r_ix, :]])
                               for op in kraus_mat_list])
                          for r_ix in op_rng]
                         for c_ix in op_rng])
    return Qobj(inpt=hstack(hstack(choi_blocks)),
                dims=[kraus_list[0].dims, kraus_list[0].dims], type='super',
                superrep='choi')


def kraus_to_super(kraus_list):
    return choi_to_super(kraus_to_choi(kraus_list))

#- PUBLIC CONVERSION FUNCTIONS ------------------------------------------------
# These functions handle superoperator conversions in a way that preserves the
# correctness of Qobj.type, and in a way that automatically branches based on
# the input Qobj.type.

def to_choi(q_oper):
    """
    Converts a Qobj representing a quantum map to the Choi representation,
    such that the trace of the returned operator is equal to the dimension
    of the system.
    
    Parameters
    ----------
    q_oper : Qobj
        Superoperator to be converted to Choi representation.
        
    Returns
    -------
    choi : Qobj
        A quantum object representing the same map as ``q_oper``, such that
        ``choi.superrep == "choi"``.
        
    Raises
    ------
    TypeError: if the given quantum object is not a map, or cannot be converted
        to Choi representation.
    """
    if q_oper.type == 'super':
        if q_oper.superrep == 'choi':
            return q_oper
        if q_oper.superrep == 'super':
            return super_to_choi(q_oper)
        else:
            raise TypeError(q_oper.superrep)
    elif q_oper.type == 'oper':
        return super_to_choi(spre(q_oper) * spost(q_oper.dag()))
    else:
        raise TypeError(
            "Conversion of Qobj with type = {0.type} "
            "and superrep = {0.choi} to Choi not supported.".format(q_oper)
        )

def to_super(q_oper):
    """
    Converts a Qobj representing a quantum map to the supermatrix (Liouville)
    representation.
    
    Parameters
    ----------
    q_oper : Qobj
        Superoperator to be converted to supermatrix representation.
        
    Returns
    -------
    superop : Qobj
        A quantum object representing the same map as ``q_oper``, such that
        ``superop.superrep == "super"``.
        
    Raises
    ------
    TypeError: if the given quantum object is not a map, or cannot be converted
        to supermatrix representation.
    """
    if q_oper.type == 'super':
        if q_oper.superrep == "super":
            return q_oper
        elif q_oper.superrep == 'choi':
            return choi_to_super(q_oper)
    elif q_oper.type == 'oper': # Assume unitary.
        return spre(q_oper) * spost(q_oper.dag())
    else:
        raise TypeError(
            "Conversion of Qobj with type = {0.type} "
            "and superrep = {0.superrep} to supermatrix not "
            "supported.".format(q_oper)
        )

def to_kraus(q_oper):
    """
    Converts a Qobj representing a quantum map to a list of quantum objects,
    each representing an operator in the Kraus decomposition of the given map.
    
    Parameters
    ----------
    q_oper : Qobj
        Superoperator to be converted to Kraus representation.
        
    Returns
    -------
    kraus_ops : list of Qobj
        A list of quantum objects, each representing a Kraus operator in the
        decomposition of ``q_oper``.
        
    Raises
    ------
    TypeError: if the given quantum object is not a map, or cannot be
        decomposed into Kraus operators.
    """
    if q_oper.type == 'super':
        if q_oper.superrep == "super":
            return to_kraus(to_choi(q_oper))
        elif q_oper.superrep == 'choi':
            return choi_to_kraus(q_oper)
    elif q_oper.type == 'oper': # Assume unitary.
        return [q_oper]
    else:
        raise TypeError(
            "Conversion of Qobj with type = {0.type} "
            "and superrep = {0.superrep} to Kraus decomposition not "
            "supported.".format(q_oper)
        )
    
