function sp = computeSpectra(data, control, fs, nfft, overlap)
%COMPUTESPECTRA Welch ASDs, H1 transmissibility and coherence vs. the control channel.
%   sp = ods.computeSpectra(data, control, fs, nfft, overlap)
%     data    : N x nch acceleration time histories (one synchronized run)
%     control : column index of the control (table) accelerometer
%     overlap : fraction, default 0.5
%
%   Returned fields: f (nf x 1, Hz), T (nf x nch complex, H1 = G_bx / G_bb),
%   coh (nf x nch), Gbb (nf x 1, units^2/Hz), Gxx (nf x nch), nfft, nAvg.
%
%   Written without the Signal Processing Toolbox and matched to scipy.signal.csd /
%   welch (periodic Hann, per-segment mean removal, density scaling, one-sided
%   doubling, mean averaging) so the Python and MATLAB versions agree to round-off.
%   H1 is unbiased by noise on the responses and biased low only by noise on the
%   control; coherence flags noise, nonlinearity and leakage.

    if nargin < 5, overlap = 0.5; end
    if overlap < 0 || overlap >= 1
        error('ods:computeSpectra', 'overlap must be in [0, 1)');
    end
    [n, nch] = size(data);
    if n < nfft
        error('ods:computeSpectra', 'Record (%d samples) shorter than nfft (%d); lower the resolution', n, nfft);
    end
    noverlap = floor(nfft * overlap);
    step = nfft - noverlap;
    nAvg = floor((n - noverlap) / step);

    w = 0.5 - 0.5 * cos(2 * pi * (0:nfft - 1)' / nfft);   % periodic Hann (scipy 'hann')
    nf = floor(nfft / 2) + 1;
    Sbx = zeros(nf, nch);
    Sxx = zeros(nf, nch);
    for s = 1:nAvg
        seg = data((s - 1) * step + (1:nfft), :);
        seg = seg - mean(seg, 1);                          % detrend='constant'
        X = fft(seg .* w);
        X = X(1:nf, :);
        Sbx = Sbx + conj(X(:, control)) .* X;              % E[conj(B) X] = G_bx
        Sxx = Sxx + abs(X) .^ 2;
    end
    scale = 1 / (fs * sum(w .^ 2));
    Gbx = Sbx / nAvg * scale;
    Gxx = Sxx / nAvg * scale;
    % One-sided: double everything except DC and (for even nfft) Nyquist.
    if mod(nfft, 2) == 0
        idx = 2:nf - 1;
    else
        idx = 2:nf;
    end
    Gbx(idx, :) = 2 * Gbx(idx, :);
    Gxx(idx, :) = 2 * Gxx(idx, :);
    Gbb = Gxx(:, control);

    T = Gbx ./ Gbb;
    coh = abs(Gbx) .^ 2 ./ (Gbb .* Gxx);
    T(~isfinite(T)) = 0;
    coh(~isfinite(coh)) = 0;
    coh = min(max(coh, 0), 1);

    sp.f = (0:nf - 1)' * fs / nfft;
    sp.T = T;
    sp.coh = coh;
    sp.Gbb = Gbb;
    sp.Gxx = Gxx;
    sp.nfft = nfft;
    sp.nAvg = nAvg;
end
