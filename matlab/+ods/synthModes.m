function modes = synthModes(model, axisVec)
%SYNTHMODES Undamped modes (mass-normalised) + band-assigned modal damping.
%   Fields: fn (Hz), zeta, phi (3n x m, phi' M phi = I), participation (phi' M r).
    [phi, L] = eig(model.K, model.M);
    [w2, order] = sort(max(real(diag(L)), 0));
    phi = real(phi(:, order));
    phi = phi ./ sqrt(diag(phi' * model.M * phi))';   % enforce mass normalisation explicitly
    modes.fn = sqrt(w2) / (2 * pi);
    modes.zeta = model.zetaElastic * ones(size(modes.fn));
    modes.zeta(modes.fn < model.rigidCutoffHz) = model.zetaRigid;
    modes.phi = phi;
    r = repmat(axisVec(:), numel(model.nodeIds), 1);
    modes.participation = phi' * model.M * r;
end
