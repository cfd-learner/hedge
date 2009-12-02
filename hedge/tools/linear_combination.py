"""Backend support for optimized linear combinations,  for timestepping."""

from __future__ import division

__copyright__ = "Copyright (C) 2007 Andreas Kloeckner"

__license__ = """
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see U{http://www.gnu.org/licenses/}.
"""




import numpy




class ObjectArrayLinearCombinationWrapper(object):
    def __init__(self, scalar_kernel):
        self.scalar_kernel = scalar_kernel

    def __call__(self, *args):
        from pytools import indices_in_shape, single_valued

        oa_shape = single_valued(ary.shape for fac, ary in args)
        result = numpy.zeros(oa_shape, dtype=object)

        for i in indices_in_shape(oa_shape):
            args_i = [(fac, ary[i]) for fac, ary in args]
            result[i] = self.scalar_kernel(*args_i)

        return result




class UnoptimizedLinearCombiner(object):
    def __init__(self, result_dtype, scalar_dtype):
        self.result_type = result_dtype.type

    def __call__(self, *args):
        return sum(self.result_type(fac)*vec for fac, vec in args)




class NumpyLinearCombiner(object):
    def __init__(self, result_dtype, scalar_dtype, sample_vec, arg_count):
        self.result_dtype = result_dtype
        self.shape = sample_vec.shape

        from codepy.elementwise import \
                make_linear_comb_kernel_with_result_dtype
        self.kernel = make_linear_comb_kernel_with_result_dtype(
                result_dtype,
                (scalar_dtype,)*arg_count,
                (sample_vec.dtype,)*arg_count)

    def __call__(self, *args):
        result = numpy.empty(self.shape, self.result_dtype)

        from pytools import flatten
        self.kernel(result, *tuple(flatten(args)))

        return result




def make_linear_combiner(result_dtype, scalar_dtype, sample_vec, arg_count, rcon=None):
    """
    :param result_dtype: dtype of the desired result.
    :param scalar_dtype: dtype of the scalars.
    :param sample_vec: must match states and right hand sides in shape, object
      array composition, and dtypes.
    :param rcon:
    :returns: a function that accepts `2*arg_count` arguments
      *((factor0, vec0), (factor1, vec1), ...)* and returns
      `factor0*vec0 + factor1*vec1`.
    """
    from hedge.tools import is_obj_array
    sample_is_obj_array = is_obj_array(sample_vec)

    if sample_is_obj_array:
        sample_vec = sample_vec[0]

    if isinstance(sample_vec, numpy.ndarray) and sample_vec.dtype != object:
        kernel = NumpyLinearCombiner(result_dtype, scalar_dtype, sample_vec,
                arg_count)
    else:
        kernel = None
        if rcon is not None:
            kernel = rcon.make_linear_combiner(result_dtype, scalar_dtype, 
                    sample_vec, arg_count)

        if kernel is None:
            from warnings import warn
            warn("using unoptimized linear combination routine")
            kernel = UnoptimizedLinearCombiner(result_dtype, scalar_dtype)

    if sample_is_obj_array:
        kernel = ObjectArrayLinearCombinationWrapper(kernel)

    return kernel