function sim = synthSimulate(model, axisName, fs, duration, seed, noiseAsd)
%SYNTHSIMULATE Simulate one base-driven random run of the synthetic model.
%   sim = ods.synthSimulate(model, 'Z', 5120, 60, 1)
%   Relative-coordinate EOM  M z'' + C z' + K z = -M r a_b  with modal damping gives the
%   absolute-acceleration transmissibility of every DOF
%       T(w) = r + w^2 * sum_n phi_n (phi_n' M r) / (w_n^2 - w^2 + 2j zeta_n w_n w).
%   Responses are made by multiplying the base spectrum by T on one full-length FFT
%   (periodic steady state, no start-up transient), then white sensor noise of one-sided
%   ASD noiseAsd (g^2/Hz, default 1e-6) is added to every channel incl. the control.
%   Random numbers differ from the Python generator, so data are statistically, not
%   sample-for-sample, equivalent.
%
%   Fields: fs, axis, data (N x nch, g), channels (struct array: channel, node,
%   direction, role), modes (fn, zeta, phi, participation), grmsInput.
    if nargin < 2 || isempty(axisName), axisName = 'Z'; end
    if nargin < 3 || isempty(fs), fs = 5120; end
    if nargin < 4 || isempty(duration), duration = 60; end
    if nargin < 5 || isempty(seed), seed = 1; end
    if nargin < 6 || isempty(noiseAsd), noiseAsd = 1e-6; end
    seedRng(seed);

    axisVec = double('XYZ' == upper(axisName));
    nNodes = numel(model.nodeIds);
    N = round(fs * duration);
    N = N + mod(N, 2);
    f = (0:N / 2)' * fs / N;

    % Complex Gaussian bins with E|X_k|^2 = S_k fs N / 2 give a one-sided ASD S_k.
    sc = sqrt(ods.navmatAsd(f) * fs * N / 4);
    Xb = sc .* (randn(size(f)) + 1i * randn(size(f)));
    Xb(1) = 0;
    Xb(end) = real(Xb(end));
    base = irfft(Xb, N);

    modes = ods.synthModes(model, axisVec);
    r = repmat(axisVec(:), nNodes, 1);
    T = ods.synthTransmissibility(modes, r, f);        % 3n x nf
    dofAcc = irfft(T.' .* Xb, N);                       % N x 3n, g

    chans = struct('channel', {['CTRL']}, 'node', {100}, 'direction', {['+' upper(axisName)]}, 'role', {'control'});
    resp = zeros(N, 3 * nNodes);
    m = 0;
    for i = 1:nNodes
        for j = 1:3
            m = m + 1;
            ax = 'XYZ';
            chans(end + 1) = struct('channel', sprintf('N%d%s', model.nodeIds(i), ax(j)), 'node', ...
                model.nodeIds(i), 'direction', ['+' ax(j)], 'role', 'response'); %#ok<AGROW>
            resp(:, m) = dofAcc(:, 3 * (i - 1) + j);
        end
    end
    data = [base, resp];
    data = data + sqrt(noiseAsd * fs / 2) * randn(size(data));

    sim.fs = fs;
    sim.axis = upper(axisName);
    sim.data = data;
    sim.channels = chans;
    sim.modes = modes;
    sim.grmsInput = std(base, 1);
end

function x = irfft(X, N)
% Inverse of a one-sided spectrum (numpy.fft.irfft for even N), column-wise.
    full = [X; conj(X(end - 1:-1:2, :))];
    x = real(ifft(full, N, 1));
end

function seedRng(seed)
    try
        rng(seed, 'twister');
    catch
        randn('state', seed); %#ok<RAND>  (Octave without rng)
    end
end
