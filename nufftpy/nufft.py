from __future__ import division, print_function
import numpy as np


def nufftfreqs(M, df=1):
    """Compute the frequency range used in nufft for M frequency bins"""
    return df * np.arange(-(M // 2), M - (M // 2))


def nufft1d(x, c, M, df=1.0, eps=1E-15, iflag=1,
            direct=False, fast_gridding=True):
    """Fast Non-Uniform Fourier Transform in 1 Dimension

    Compute the non-uniform FFT of one-dimensional points x with complex
    values c. Result is computed at frequencies (df * m)
    for integer m in the range -M/2 < m < M/2.

    Parameters
    ----------
    x, c : array_like
        real locations x and complex values c of the points to be transformed.
    M, df : int & float
        Parameters specifying the desired frequency grid. Transform will be
        computed at frequencies df * (-(M//2) + arange(M))
    eps : float
        The desired approximate error for the FFT result. Must be in range
        1E-33 < eps < 1E-1, though be aware that the errors are only well
        calibrated near the range 1E-12 ~ 1E-6. eps is not referenced if
        direct = True.
    iflag : float
        if iflag<0, compute the transform with a negative exponent.
        if iflag>=0, compute the transform with a positive exponent.
    direct : bool (default = False)
        If True, then use the slower (but more straightforward)
        direct Fourier transform to compute the result.
    fast_gridding : bool (default = True)
        If True, use the fast Gaussian grid algorithm of Greengard & Lee (2004)
        Otherwise, use a more naive gridding approach

    Returns
    -------
    Fk : ndarray
        The complex discrete Fourier transform

    See Also
    --------
    nufftfreqs : compute the frequencies of the nufft results
    """
    # Check inputs
    x = np.asarray(x, dtype=float)
    c = np.asarray(c, dtype=complex)
    if x.ndim != 1:
        raise ValueError("Expected one-dimensional input arrays")
    if x.shape != c.shape:
        raise ValueError("Array shapes must match")
    sign = -1 if iflag < 0 else 1
    M = int(M)

    if direct:
        # Direct Fourier Transform: this is easy (but slow)
        return (1 / M) * np.dot(c, np.exp(sign * 1j *
                                          nufftfreqs(M, df) * x[:, None]))
    else:
        # Fast Fourier Transform: this is more involved
        N = len(x)
        if eps <= 1E-33 or eps >= 1E-1:
            raise ValueError("eps = {0:.0e}; must satisfy "
                             "1e-33 < eps < 1e-1.".format(eps))

        # Choose Msp & tau from eps following Dutt & Rokhlin (1993)
        ratio = 2 if eps > 1E-11 else 3
        Msp = int(-np.log(eps) / (np.pi * (ratio - 1) / (ratio - 0.5)) + 0.5)
        Mr = max(ratio * M, 2 * Msp)
        lambda_ = Msp / (ratio * (ratio - 0.5))
        tau = np.pi * lambda_ / M ** 2

        # Construct the convolved grid
        ftau = np.zeros(Mr, dtype=c.dtype)
        hx = 2 * np.pi / Mr
        xmod = (df * x) % (2 * np.pi)

        m = 1 + (xmod // hx).astype(int)
        msp = np.arange(-Msp, Msp)[:, np.newaxis]
        mm = m + msp

        if fast_gridding:
            # Greengard & Lee (2004) approach
            E1 = np.exp(-0.25 * (xmod - hx * m) ** 2 / tau)
            
            # Following basically computes this:
            # E2 = np.exp(msp * (xmod - hx * m) * np.pi / (Mr * tau))
            E2 = np.empty((2 * Msp, N), dtype=xmod.dtype)
            E2[Msp] = 1
            E2[Msp + 1:] = np.exp((xmod - hx * m) * np.pi / (Mr * tau))
            E2[Msp + 1:].cumprod(0, out=E2[Msp + 1:])
            E2[Msp - 1::-1] = 1. / (E2[Msp + 1] * E2[Msp:])
            
            E3 = np.exp(-(np.pi * msp / Mr) ** 2 / tau)
            spread = (c * E1) * E2 * E3
        else:
            spread = c * np.exp(-0.25 * (xmod - hx * mm) ** 2 / tau)
        np.add.at(ftau, mm % Mr, spread)

        # Compute the FFT on the convolved grid
        if sign < 0:
            Ftau = (1 / Mr) * np.fft.fft(ftau)
        else:
            Ftau = np.fft.ifft(ftau)
        Ftau = np.concatenate([Ftau[-(M//2):], Ftau[:M//2 + M % 2]])

        # Deconvolve the grid using convolution theorem
        k = nufftfreqs(M)
        return (1 / M) * np.sqrt(np.pi / tau) * np.exp(tau * k ** 2) * Ftau
