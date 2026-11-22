function peaks = findPeaks(f, T, coh, band, prominenceDb, minCoh, minSpacingHz)
%FINDPEAKS Pick ODS frequencies from the channel-norm of the absolute transmissibility.
%   peaks = ods.findPeaks(f, T, coh, band, prominenceDb, minCoh, minSpacingHz)
%     T, coh : nf x k (response channels only)
%   Returns a struct array with fields index (1-based bin), f, indicatorDb, coh, mpc.
%
%   Absolute T is used deliberately: above an isolation frequency the unit is nearly
%   still, so T - 1 sits at a flat ~-1 floor that buries elastic resonances. The
%   coherence gate is weighted by |T|^2 ("are the channels carrying this shape
%   trustworthy?"); a plain mean is dragged down by quiet noise-floor channels.
%
%   The peak search reproduces scipy.signal.find_peaks(x, distance=..., prominence=...)
%   without the Signal Processing Toolbox: local maxima (plateau midpoints), then the
%   distance filter (highest first), then prominence. The only possible difference is
%   the order of two peaks with bit-identical heights inside the distance window (scipy
%   sorts them unstably), which does not occur with measured spectra.

    if nargin < 5, prominenceDb = 3; end
    if nargin < 6, minCoh = 0.5; end
    if nargin < 7, minSpacingHz = 3; end

    power = abs(T) .^ 2;
    indDb = 20 * log10(max(sqrt(sum(power, 2)), 1e-12));
    inBand = f >= band(1) & f <= band(2);
    x = indDb;
    x(~inBand) = -Inf;
    df = f(2) - f(1);
    distance = max(1, round(minSpacingHz / df));

    pk = localMaxima(x);
    pk = selectByDistance(x, pk, distance);
    pk = pk(prominences(x, pk) >= prominenceDb);

    wCoh = sum(power .* coh, 2) ./ max(sum(power, 2), 1e-30);
    peaks = struct('index', {}, 'f', {}, 'indicatorDb', {}, 'coh', {}, 'mpc', {});
    for k = pk(:)'
        if inBand(k) && wCoh(k) >= minCoh
            peaks(end + 1) = struct('index', k, 'f', f(k), 'indicatorDb', indDb(k), ...
                'coh', wCoh(k), 'mpc', ods.mpc(T(k, :))); %#ok<AGROW>
        end
    end
end

function pk = localMaxima(x)
% Indices of local maxima; flat tops report their (floor) midpoint, as scipy does.
    n = numel(x);
    pk = zeros(0, 1);
    i = 2;
    while i < n
        if x(i - 1) < x(i)
            ahead = i + 1;
            while ahead < n && x(ahead) == x(i)
                ahead = ahead + 1;
            end
            if x(ahead) < x(i)
                left = i - 1;      % 0-based arithmetic below to match scipy's midpoint
                right = ahead - 2;
                pk(end + 1, 1) = floor((left + right) / 2) + 1; %#ok<AGROW>
                i = ahead;
            end
        end
        i = i + 1;
    end
end

function keep = selectByDistance(x, pk, distance)
% Remove peaks closer than `distance` samples to a higher peak (higher peaks win).
    n = numel(pk);
    keepMask = true(n, 1);
    [~, order] = sort(x(pk), 'ascend');
    for j = order(end:-1:1)'
        if ~keepMask(j), continue; end
        k = j - 1;
        while k >= 1 && pk(j) - pk(k) < distance
            keepMask(k) = false;
            k = k - 1;
        end
        k = j + 1;
        while k <= n && pk(k) - pk(j) < distance
            keepMask(k) = false;
            k = k + 1;
        end
    end
    keep = pk(keepMask);
end

function prom = prominences(x, pk)
% Topographic prominence with an unbounded window (scipy wlen=None).
    n = numel(x);
    prom = zeros(size(pk));
    for m = 1:numel(pk)
        p = pk(m);
        leftMin = x(p);
        i = p;
        while i >= 1 && x(i) <= x(p)
            leftMin = min(leftMin, x(i));
            i = i - 1;
        end
        rightMin = x(p);
        i = p;
        while i <= n && x(i) <= x(p)
            rightMin = min(rightMin, x(i));
            i = i + 1;
        end
        prom(m) = x(p) - max(leftMin, rightMin);
    end
end
