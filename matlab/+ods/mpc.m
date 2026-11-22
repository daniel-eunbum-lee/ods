function v = mpc(shape)
%MPC Modal phase collinearity (Pappa et al. 1993), 0..1.
%   Eigenvalues of the 2x2 covariance of (Re, Im): if all points lie on one line through
%   the origin of the complex plane the shape is a standing (real) wave and MPC = 1.
%   Deliberately not mean-centred: a line through the origin is what makes a standing
%   wave. Low MPC means closely spaced modes or non-proportional damping.
    z = shape(:);
    re = real(z);
    im = imag(z);
    C = [re' * re, re' * im; re' * im, im' * im];
    lam = sort(eig(C));
    total = sum(lam);
    if total > 0
        v = ((lam(2) - lam(1)) / total) ^ 2;
    else
        v = 1;
    end
end
