function R = rigidBodyProjector(positions, dirs)
%RIGIDBODYPROJECTOR k x k matrix that removes least-squares 6-DOF rigid-body motion.
%   A rigid motion (translation t, small rotation theta) is read by a sensor at p with
%   direction d as d.t + d.(theta x p) = d.t + theta.(p x d). Stacking those rows gives
%   A (k x 6); R = I - A*pinv(A) leaves only the elastic (deforming) part. Positions are
%   taken about their centroid for conditioning. Needs >= 6 well-spread channels to remove
%   all six rigid-body DOFs; with fewer, the pseudo-inverse removes what is observable.
    p = positions - mean(positions, 1);
    A = [dirs, cross(p, dirs, 2)];
    tol = 1e-8 * max(svd(A));   % relative cutoff, as numpy.linalg.pinv(rcond=1e-8)
    R = eye(size(dirs, 1)) - A * pinv(A, tol);
end
