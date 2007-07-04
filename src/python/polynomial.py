from __future__ import division
import pylinear.array as num
from pytools import memoize
import hedge._internal




jacobi_function = hedge._internal.JacobiPolynomial




@memoize
def diff_jacobi_polynomial(alpha, beta, N):
    from math import sqrt

    if N == 0:
        return 0
    else:
        return sqrt(N*(N+alpha+beta+1))*\
                jacobi_polynomial(alpha+1, beta+1, N-1)




class diff_jacobi_function:
    def __init__(self, alpha, beta, N):
        from math import sqrt
        if N == 0:
            self.jf = lambda x: 0
            self.factor = 0
        else:
            self.jf = jacobi_function(alpha+1, beta+1, N-1)
            self.factor = sqrt(N*(N+alpha+beta+1))

    def __call__(self, x):
        return self.factor*self.jf(x)

@memoize
def diff_jacobi_function_2(alpha, beta, N):
    return pymbolic.compile(diff_jacobi_polynomial(alpha, beta, N), ["x"])




def legendre_polynomial(N):
    return jacobi_polynomial(0, 0, N)




def diff_legendre_polynomial(N, derivative=1):
    return diff_jacobi_polynomial(0, 0, N, derivative)




def legendre_function(N):
    return jacobi_function(0, 0, N)




def diff_legendre_function(N):
    return diff_jacobi_function(0, 0, N)




def generic_vandermonde(points, functions):
    """Return a Vandermonde matrix
      V[i,j] := f[j](x[i])
    where functions=[f[j] for j] and points=[x[i] for i].
    """
    v = num.zeros((len(points), len(functions)))
    for i, x in enumerate(points):
        for j, f in enumerate(functions):
            v[i,j] = f(x)
    return v




def generic_multi_vandermonde(points, functions):
    """Return multiple Vandermonde matrices.
      V[i,j] := f[j](x[i])
    where functions=[f[j] for j] and points=[x[i] for i].
    The functions `f' are multi-valued, one matrix is returned
    for each return value.
    """
    count = len(functions[0](points[0]))
    result = [num.zeros((len(points), len(functions))) for n in range(count)]

    for i, x in enumerate(points):
        for j, f in enumerate(functions):
            for n, f_n in enumerate(f(x)):
                result[n][i,j] = f_n
    return result




def legendre_vandermonde(points, N):
    return generic_vandermonde(points, 
            [legendre_function(i) for i in range(N+1)])
