# This file is part of QuTiP: Quantum Toolbox in Python.
#
#    Copyright (c) 2011 and later, Paul D. Nation and Robert J. Johansson.
#    All rights reserved.
#
#    Redistribution and use in source and binary forms, with or without
#    modification, are permitted provided that the following conditions are
#    met:
#
#    1. Redistributions of source code must retain the above copyright notice,
#       this list of conditions and the following disclaimer.
#
#    2. Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#
#    3. Neither the name of the QuTiP: Quantum Toolbox in Python nor the names
#       of its contributors may be used to endorse or promote products derived
#       from this software without specific prior written permission.
#
#    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#    "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#    LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
#    PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#    HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#    SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#    LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#    DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#    THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#    (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#    OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
###############################################################################
"""
Module for the creation of composite quantum objects via the tensor product.
"""

__all__ = ['tensor', 'super_tensor', 'composite']

import numpy as np
import scipy.sparse as sp

from qutip.qobj import Qobj
from qutip.permute import reshuffle
from qutip.superoperator import operator_to_vector

import qutip.settings
import qutip.superop_reps  # Avoid circular dependency here.


def tensor(*args):
    """Calculates the tensor product of input operators.

    Parameters
    ----------
    args : array_like
        ``list`` or ``array`` of quantum objects for tensor product.

    Returns
    -------
    obj : qobj
        A composite quantum object.

    Examples
    --------
    >>> tensor([sigmax(), sigmax()])
    Quantum object: dims = [[2, 2], [2, 2]], \
shape = [4, 4], type = oper, isHerm = True
    Qobj data =
    [[ 0.+0.j  0.+0.j  0.+0.j  1.+0.j]
     [ 0.+0.j  0.+0.j  1.+0.j  0.+0.j]
     [ 0.+0.j  1.+0.j  0.+0.j  0.+0.j]
     [ 1.+0.j  0.+0.j  0.+0.j  0.+0.j]]
    """

    if not args:
        raise TypeError("Requires at least one input argument")

    if len(args) == 1 and isinstance(args[0], (list, np.ndarray)):
        # this is the case when tensor is called on the form:
        # tensor([q1, q2, q3, ...])
        qlist = args[0]

    elif len(args) == 1 and isinstance(args[0], Qobj):
        # tensor is called with a single Qobj as an argument, do nothing
        return args[0]

    else:
        # this is the case when tensor is called on the form:
        # tensor(q1, q2, q3, ...)
        qlist = args

    if not all([isinstance(q, Qobj) for q in qlist]):
        # raise error if one of the inputs is not a quantum object
        raise TypeError("One of inputs is not a quantum object")

    out = Qobj()

    if qlist[0].issuper:
        out.superrep = qlist[0].superrep
        if not all([q.superrep == out.superrep for q in qlist]):
            raise TypeError("In tensor products of superroperators, all must" +
                            "have the same representation")

    out.isherm = True
    for n, q in enumerate(qlist):
        if n == 0:
            out.data = q.data
            out.dims = q.dims
        else:
            out.data = sp.kron(out.data, q.data, format='csr')
            out.dims = [out.dims[0] + q.dims[0], out.dims[1] + q.dims[1]]

        out.isherm = out.isherm and q.isherm

    if not out.isherm:
        out._isherm = None

    return out.tidyup() if qutip.settings.auto_tidyup else out


def super_tensor(*args):
    """Calculates the tensor product of input superoperators, by tensoring
    together the underlying Hilbert spaces on which each vectorized operator
    acts.

    Parameters
    ----------
    args : array_like
        ``list`` or ``array`` of quantum objects with ``type="super"``.

    Returns
    -------
    obj : qobj
        A composite quantum object.

    """
    if isinstance(args[0], list):
        args = args[0]

    # Check if we're tensoring vectors or superoperators.
    if all(arg.issuper for arg in args):
        if not all(arg.superrep == "super" for arg in args):
            raise TypeError(
                "super_tensor on type='super' is only implemented for "
                "superrep='super'."
            )

        # Reshuffle the superoperators.
        shuffled_ops = list(map(reshuffle, args))

        # Tensor the result.
        shuffled_tensor = tensor(shuffled_ops)

        # Unshuffle and return.
        out = reshuffle(shuffled_tensor)
        out.superrep = args[0].superrep
        return out

    elif all(arg.isoperket for arg in args):

        # Reshuffle the superoperators.
        shuffled_ops = list(map(reshuffle, args))

        # Tensor the result.
        shuffled_tensor = tensor(shuffled_ops)

        # Unshuffle and return.
        out = reshuffle(shuffled_tensor)
        return out

    elif all(arg.isoperbra for arg in args):
        return super_tensor(*(arg.dag() for arg in args)).dag()

    else:
        raise TypeError(
            "All arguments must be the same type, "
            "either super, operator-ket or operator-bra."
        )


def _isoperlike(q):
    return q.isoper or q.issuper


def _isketlike(q):
    return q.isket or q.isoperket


def _isbralike(q):
    return q.isbra or q.isoperbra


def composite(*args):
    """
    Given two or more operators, kets or bras, returns the Qobj
    corresponding to a composite system over each argument.
    For ordinary operators and vectors, this is the tensor product,
    while for superoperators and vectorized operators, this is
    the column-reshuffled tensor product.

    If a mix of Qobjs supported on Hilbert and Liouville spaces
    are passed in, the former are promoted. Ordinary operators
    are assumed to be unitaries, and are promoted using ``to_super``,
    while kets and bras are promoted by taking their projectors and
    using ``operator_to_vector(ket2dm(arg))``.
    """
    # First step will be to ensure everything is a Qobj at all.
    if not all(isinstance(arg, Qobj) for arg in args):
        raise TypeError("All arguments must be Qobjs.")

    # Next, figure out if we have something oper-like (isoper or issuper),
    # or something ket-like (isket or isoperket). Bra-like we'll deal with
    # by turning things into ket-likes and back.
    if all(map(_isoperlike, args)):
        # OK, we have oper/supers.
        if any(arg.issuper for arg in args):
            # Note that to_super does nothing to things
            # that are already type=super, while it will
            # promote unitaries to superunitaries.
            return super_tensor(*map(qutip.superop_reps.to_super, args))

        else:
            # Everything's just an oper, so ordinary tensor products work.
            return tensor(*args)

    elif all(map(_isketlike, args)):
        # Ket-likes.
        if any(arg.isoperket for arg in args):
            # We have a vectorized operator, we we may need to promote
            # something.
            return super_tensor(*(
                arg if arg.isoperket else operator_to_vector(qutip.states.ket2dm(arg))
                for arg in args
            ))

        else:
            # Everything's ordinary, so we can use the tensor product here.
            return tensor(*args)

    elif all(map(_isbralike, args)):
        # Turn into ket-likes and recurse.
        return composite(*(arg.dag() for arg in args)).dag()

    else:
        raise TypeError("Unsupported Qobj types [{}].".format(
            ", ".join(arg.type for arg in args)
        ))

import qutip.states
