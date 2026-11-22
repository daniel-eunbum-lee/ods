function run_tests()
%RUN_TESTS Test suite for the MATLAB ODS port (works in MATLAB and GNU Octave).
%   From the repository root:   addpath matlab/tests; run_tests
%   Uses plain asserts (no matlab.unittest) so Octave can run it too. Includes a parity
%   test against results produced by the Python implementation on the same data
%   (fixtures/parity, regenerate with `uv run python matlab/tests/make_parity_fixture.py`).
    here = fileparts(mfilename('fullpath'));
    addpath(fullfile(here, '..'));
    tests = {@testSdofH1, @testSpectraErrors, @testRelativeTransmissibility, @testDisplacementUnits, ...
        @testMpcMac, @testRigidBodyProjector, @testNodeProjectors, @testParseDirection, ...
        @testFindPeaksPlateau, @testFindPeaksBandEdge, @testSplitCsvLine, ...
        @testSynthModel, @testModalTransmissibility, ...
        @testParityWithPython, @testEndToEndSynthetic};
    nFail = 0;
    for i = 1:numel(tests)
        name = func2str(tests{i});
        try
            tests{i}();
            fprintf('  PASS  %s\n', name);
        catch err
            nFail = nFail + 1;
            fprintf('  FAIL  %s\n        %s\n', name, err.message);
        end
    end
    fprintf('%d passed, %d failed\n', numel(tests) - nFail, nFail);
    if nFail > 0
        error('ods:tests', '%d test(s) failed', nFail);
    end
end

% ------------------------------------------------------------------ helpers

function check(cond, msg, varargin)
    if ~cond
        error('ods:check', msg, varargin{:});
    end
end

function checkClose(a, b, rtol, atol, what)
    check(numel(a) == numel(b), '%s: %d vs %d elements', what, numel(a), numel(b));
    bad = find(isnan(a(:)) ~= isnan(b(:)), 1);   % max() skips NaN, so check it explicitly
    check(isempty(bad), '%s: element %d is NaN in only one input', what, bad);
    err = abs(a(:) - b(:));
    err(isnan(err)) = 0;                          % NaN in both: treat as equal
    tol = atol + rtol * abs(b(:));
    if isempty(err), return; end
    [worst, i] = max(err - tol);
    check(worst <= 0, '%s: element %d differs by %.3g (tol %.3g)', what, i, err(i), tol(i));
end

function T = sdofT(f, fn, zeta)
    w = 2 * pi * f; wn = 2 * pi * fn;
    T = (wn ^ 2 + 2i * zeta * wn * w) ./ (wn ^ 2 - w .^ 2 + 2i * zeta * wn * w);
end

% ------------------------------------------------------------------ spectra

function testSdofH1()
    fs = 2048; n = 2 ^ 18; fn = 100; zeta = 0.05;
    try, rng(0); catch, randn('state', 0); end %#ok<RAND>
    b = randn(n, 1);
    fFull = (0:n / 2)' * fs / n;
    B = fft(b);
    H = sdofT(fFull, fn, zeta);
    Y = B(1:n / 2 + 1) .* H;
    x = real(ifft([Y; conj(Y(end - 1:-1:2))]));
    x = x + 1e-3 * randn(n, 1);
    sp = ods.computeSpectra([b, x], 1, fs, 2048);
    band = sp.f > 10 & sp.f < 800;
    Ttrue = sdofT(sp.f(band), fn, zeta);
    relErr = abs(sp.T(band, 2) - Ttrue) ./ abs(Ttrue);
    check(median(relErr) < 0.01, 'median H1 error %.3g', median(relErr));
    check(max(relErr) < 0.08, 'max H1 error %.3g', max(relErr));
    checkClose(sp.T(band, 1), ones(nnz(band), 1), 0, 1e-12, 'control vs itself');
    check(min(sp.coh(band, 2)) > 0.98, 'coherence %.3f', min(sp.coh(band, 2)));
end

function testSpectraErrors()
    threw = false;
    try
        ods.computeSpectra(zeros(100, 2), 1, 1000, 256);
    catch
        threw = true;
    end
    check(threw, 'short record should raise');
end

% ------------------------------------------------------------------ shapes

function testRelativeTransmissibility()
    T = ones(4, 3);
    dirs = [0 0 1; 1 0 0; 0 -0.6 0.8];
    rel = ods.relativeTransmissibility(T, dirs, [0 0 1]);
    checkClose(rel(1, :), [0 1 0.2], 0, 1e-12, 'relative T');
end

function testDisplacementUnits()
    d = ods.accelToDisplacement([1; 1], [0; 10], 'g');
    check(d(1) == 0, 'DC bin should be 0');
    checkClose(d(2), -9.80665 / (2 * pi * 10) ^ 2 * 1e3, 1e-12, 0, '1 g at 10 Hz');
    checkClose(d(2), -2.484, 0, 1e-3, '1 g at 10 Hz in mm');
    dSi = ods.accelToDisplacement([1; 1], [0; 10], 'm/s^2');
    checkClose(dSi(2), d(2) / 9.80665, 1e-12, 0, 'SI units');
end

function testMpcMac()
    realShape = [1 -2 0.5] * exp(0.7i);
    checkClose(ods.mpc(realShape), 1, 1e-12, 0, 'MPC of rotated real shape');
    checkClose(ods.mpc([1 1i -1 -1i]), 0, 0, 1e-12, 'MPC of travelling wave');
    checkClose(ods.mac(realShape, 3 * realShape), 1, 1e-12, 0, 'MAC self');
    checkClose(ods.mac([1 0], [0 1]), 0, 0, 1e-15, 'MAC orthogonal');
end

function testRigidBodyProjector()
    try, rng(2); catch, randn('state', 2); end %#ok<RAND>
    pos = repelem(2 * rand(5, 3) - 1, 3, 1);
    dirs = repmat(eye(3), 5, 1);
    R = ods.rigidBodyProjector(pos, dirs);
    t = randn(1, 3); th = randn(1, 3);
    rigid = sum(dirs .* (t + cross(repmat(th, 15, 1), pos - mean(pos, 1), 2)), 2);
    checkClose(R * rigid, zeros(15, 1), 0, 1e-10, 'rigid motion removed');
    checkClose(trace(R), 15 - 6, 0, 1e-9, 'projector rank');
end

function testNodeProjectors()
    dirs = [1 0 0; 0 1 0; 0 0 1; 0 0 -1];
    proj = ods.nodeProjectors([1; 2], [1; 1; 1; 2], dirs, 1:4);
    checkClose(proj(1).P * [1; 2; 3], [1; 2; 3], 0, 1e-12, 'triax node');
    checkClose(proj(2).P * 4, [0; 0; -4], 0, 1e-12, 'single -Z sensor');
end

function testParseDirection()
    checkClose(ods.parseDirection('-y'), [0 -1 0], 0, 0, '-y');
    checkClose(ods.parseDirection('1 1 0'), [1 1 0] / sqrt(2), 0, 1e-15, 'vector');
    threw = false;
    try, ods.parseDirection('Q'); catch, threw = true; end
    check(threw, 'bad direction should raise');
end

function testFindPeaksPlateau()
    % One isolated peak with a 3-bin flat top; expect its (floor) midpoint, as scipy.
    f = (0:99)';
    x = zeros(100, 1); x(40:42) = 10; x(39) = 5; x(43) = 5;
    T = 10 .^ (x / 20);
    peaks = ods.findPeaks(f, T, ones(100, 1), [0 99], 3, 0.5, 1);
    check(numel(peaks) == 1 && peaks(1).index == 41, 'plateau peak index');
end

function testFindPeaksBandEdge()
    % A curve falling across the band edge must not report a peak at the first in-band bin.
    f = (0:199)';
    x = -0.2 * f; x(120:122) = x(120:122) + [6; 12; 6];   % bump centred on f = 120 Hz
    T = 10 .^ (x / 20);
    peaks = ods.findPeaks(f, T, ones(200, 1), [60 199], 3, 0.5, 1);
    check(numel(peaks) == 1 && peaks(1).f == 120, 'band-edge peaks: %s', mat2str([peaks.f]));
end

function testSplitCsvLine()
    p = ods.splitCsvLine(' a , "b,c" ,"say ""hi""",');
    check(isequal(p, {'a', 'b,c', 'say "hi"', ''}), 'splitCsvLine: %s', strjoin(p, '|'));
end

% ------------------------------------------------------------------ synthetic model

function testSynthModel()
    m = ods.synthBoxModel();
    checkClose(m.K, m.K.', 0, 1e-6, 'K symmetric');
    check(min(eig(m.K)) > 0, 'isolators ground every rigid-body DOF');
    checkClose(trace(m.M) / 3, 3.8, 1e-12, 0, 'total mass');
    modes = ods.synthModes(m, [0 0 1]);
    checkClose(modes.fn(3), 54.6, 0, 0.1, 'bounce frequency');
    checkClose(modes.phi.' * m.M * modes.phi, eye(27), 0, 1e-9, 'mass normalisation');
end

function testModalTransmissibility()
    modes = struct('fn', 50, 'zeta', 0.03, 'phi', 1, 'participation', 1);
    f = linspace(1, 500, 200)';
    T = ods.synthTransmissibility(modes, 1, f);
    checkClose(T(:), sdofT(f, 50, 0.03), 1e-12, 1e-12, 'modal = classic SDOF');
end

% ------------------------------------------------------------------ parity + end to end

function testParityWithPython()
    here = fileparts(mfilename('fullpath'));
    fx = fullfile(here, 'fixtures', 'parity');
    ex = load(fullfile(fx, 'expected.mat'));
    test = ods.loadTest(fx);
    res = ods.runPipeline(test, struct('df', ex.df, 'band', ex.band(:)'));
    check(res.sp.nfft == ex.nfft && res.sp.nAvg == ex.n_avg, 'nfft/averages');
    checkClose(res.sp.f, ex.f(:), 1e-12, 0, 'f');
    checkClose(res.sp.T, ex.T, 1e-9, 1e-12, 'T');
    checkClose(res.sp.coh, ex.coh, 0, 1e-9, 'coherence');
    checkClose(res.sp.Gxx, ex.Gxx, 1e-9, 0, 'Gxx');
    checkClose(res.sp.Gbb, ex.Gbb(:), 1e-9, 0, 'Gbb');
    checkClose(res.Trel, ex.T_rel, 1e-9, 1e-12, 'T_rel');
    checkClose(res.Tel, ex.T_el, 1e-7, 1e-10, 'T_el');
    checkClose(res.rigidR, ex.rigid_R, 0, 1e-9, 'rigid_R');
    checkClose(res.dispEl, ex.disp_el, 1e-7, 1e-10, 'disp_el');
    check(isequal([res.peaks.index], ex.peak_index(:)'), 'peak bins %s vs %s', ...
        mat2str([res.peaks.index]), mat2str(ex.peak_index(:)'));
    checkClose([res.peaks.f], ex.peak_f(:)', 1e-12, 0, 'peak f');
    checkClose([res.peaks.mpc], ex.peak_mpc(:)', 1e-7, 1e-9, 'peak MPC');
    checkClose([res.peaks.coh], ex.peak_coh(:)', 1e-9, 1e-12, 'peak coherence');
end

function testEndToEndSynthetic()
    model = ods.synthBoxModel();
    sim = ods.synthSimulate(model, 'Z', 5120, 20, 3);
    checkClose(sim.grmsInput, 6.06, 0.03, 0, 'input grms');
    d = tempname();
    ods.synthWriteTest(d, model, sim);
    res = ods.runPipeline(ods.loadTest(d), struct('df', 1.25));
    tr = load(fullfile(d, 'truth.mat'));
    resp = res.test.responses;
    rows = zeros(numel(resp), 1);
    for m = 1:numel(resp)
        c = resp(m);
        [~, a] = max(abs(res.test.channelDirs(c, :)));
        rows(m) = 3 * (res.test.channelNodes(c) - 1) + a;
    end
    df = res.sp.f(2);
    cases = {54.6, 'rel', 0.99; 283.3, 'el', 0.98; 348.7, 'el', 0.93};
    for i = 1:size(cases, 1)
        [fn, view, macMin] = cases{i, :};
        [~, p] = min(abs([res.peaks.f] - fn));
        pk = res.peaks(p);
        check(abs(pk.f - fn) <= 1.5 * df, 'peak near %.1f Hz found at %.2f', fn, pk.f);
        [~, j] = min(abs(tr.fn - fn));
        phi = tr.phi(rows, j);
        if strcmp(view, 'rel')
            v = ods.mac(res.disp(pk.index, resp), phi);
        else
            v = ods.mac(res.dispEl(pk.index, resp), res.rigidR * phi);
        end
        check(v > macMin, 'MAC at %.1f Hz = %.3f (< %.2f)', fn, v, macMin);
    end
    % exports + viewer
    out = fullfile(d, 'out');
    files = ods.exportResults(res, out);
    check(numel(files) == 5, 'export file count');
    html = ods.readText(ods.buildViewer(res, fullfile(out, 'v.html'), 'test'));
    check(isempty(strfind(html, '/*__ODS_DATA__*/')), 'placeholder replaced'); %#ok<STREMP>
    check(~isempty(strfind(html, '"rigidR"')), 'viewer data embedded'); %#ok<STREMP>
    rmdir(d, 's');
end
