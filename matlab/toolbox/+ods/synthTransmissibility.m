function T = synthTransmissibility(modes, r, f)
%SYNTHTRANSMISSIBILITY Exact absolute-acceleration transmissibility of every DOF.
%   T = ods.synthTransmissibility(modes, r, f) -> 3n x nf (dimensionless)
%   T(w) = r + w^2 * sum_n phi_n (phi_n' M r) / (w_n^2 - w^2 + 2j zeta_n w_n w)
%   Looping over modes keeps memory at 3n x nf rather than 3n x m x nf.
    w = 2 * pi * f(:)';
    wn = 2 * pi * modes.fn;
    T = repmat(r(:), 1, numel(w)) + 0i;
    for k = 1:numel(wn)
        h = w .^ 2 ./ (wn(k) ^ 2 - w .^ 2 + 2i * modes.zeta(k) * wn(k) * w);
        T = T + (modes.phi(:, k) * modes.participation(k)) * h;
    end
end
