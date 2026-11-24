function run_tests()
%RUN_TESTS Test suite for the MATLAB ODS port (works in MATLAB and GNU Octave).
%   From the repository root:   addpath matlab/tests; run_tests   (or: cd matlab; buildtool test)
%   Uses plain asserts (no matlab.unittest) so Octave can run it too. Includes a parity
%   test against results produced by the Python implementation on the same data
%   (testdata/data/parity, regenerate with `cd python && uv run python ../testdata/generate/make_parity_fixture.py`).
    here = fileparts(mfilename('fullpath'));
    addpath(fullfile(here, '..', 'toolbox'));
    tests = {@testSdofH1, @testSpectraErrors, @testRelativeTransmissibility, @testDisplacementUnits, ...
        @testMpcMac, @testRigidBodyProjector, @testNodeProjectors, @testParseDirection, ...
        @testFindPeaksPlateau, @testFindPeaksBandEdge, @testSplitCsvLine, @testSkewedControl, ...
        @testExcitationAxis, @testUntrustedInput, @testSafeOutput, ...
        @testSynthModel, @testModalTransmissibility, ...
        @testSharedCases, @testEndToEndSynthetic};
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

function testSkewedControl()
    % A control tilted to read g = +/-0.8 of the table must give the same views (issue #12).
    here = fileparts(mfilename('fullpath'));
    test = ods.loadTest(fullfile(here, '..', '..', 'testdata', 'data', 'parity'));
    opts = struct('df', 4, 'band', [20 450]);
    base = ods.runPipeline(test, opts);
    resp = test.responses;
    for g = [0.8, -0.8]
        sk = test;
        sk.data(:, sk.control) = g * sk.data(:, sk.control);
        sk.channelDirs(sk.control, :) = [0.6 0 g];
        r = ods.runPipeline(sk, opts);
        checkClose(r.sp.T(:, resp), base.sp.T(:, resp), 1e-9, 1e-12, sprintf('T, g = %g', g));
        checkClose(r.Trel, base.Trel, 1e-9, 1e-12, sprintf('T_rel, g = %g', g));
        checkClose(r.Tel, base.Tel, 1e-9, 1e-12, sprintf('T_el, g = %g', g));
        checkClose(r.sp.T(2:end, sk.control), g * ones(numel(r.sp.f) - 1, 1), 0, 1e-12, ...
            sprintf('control column, g = %g', g));
    end
end

function testExcitationAxis()
    % Signed axes are accepted; anything else must raise instead of silently using the control's direction.
    here = fileparts(mfilename('fullpath'));
    d = tempname();
    copyfile(fullfile(here, '..', '..', 'testdata', 'data', 'parity'), d);
    cleaner = onCleanup(@() rmdir(d, 's'));
    good = {'"-z"', [0 0 -1]; '"+Z"', [0 0 1]; '" z "', [0 0 1]; 'null', [0 0 1]};   % null = not set -> control's +Z
    for i = 1:size(good, 1)
        writeJson(d, good{i, 1});
        t = ods.loadTest(d);
        checkClose(t.excitation, good{i, 2}, 0, 0, ['excitation_axis ' good{i, 1}]);
    end
    for bad = {'"vertical"', '""', '"--Z"', '"+-Z"', '90', '["Z"]', 'true', '{}'}
        writeJson(d, bad{1});
        threw = false;
        try
            ods.loadTest(d);
        catch err
            threw = ~isempty(strfind(err.message, 'excitation_axis')); %#ok<STREMP>
        end
        check(threw, 'excitation_axis %s should raise', bad{1});
    end
end

function writeJson(d, axisJson)
    fid = fopen(fullfile(d, 'test.json'), 'w');
    fprintf(fid, '{"fs": 1024, "units": "g", "excitation_axis": %s, "time_file": "time.mat"}', axisJson);
    fclose(fid);
end

function writeTimeFileJson(d, timeFileJson)
    fid = fopen(fullfile(d, 'test.json'), 'w');
    fprintf(fid, '{"fs": 1024, "units": "g", "excitation_axis": "Z", "time_file": %s}', timeFileJson);
    fclose(fid);
end

function checkLoadFails(d, what, msgPart)
    threw = false;
    try
        ods.loadTest(d);
    catch err
        threw = strcmp(err.identifier, 'ods:loadTest') && ~isempty(strfind(err.message, msgPart)); %#ok<STREMP>
    end
    check(threw, '%s should be rejected with a message containing "%s"', what, msgPart);
end

function testUntrustedInput()
    % A test folder may come from someone else (Python: tests/test_input_safety.py). time_file must
    % stay inside the folder, the .mat may only hold numeric data/fs and text channels, and the
    % geometry must be finite.
    here = fileparts(mfilename('fullpath'));
    src = fullfile(here, '..', '..', 'testdata', 'data', 'parity');
    d = tempname();
    copyfile(src, d);
    cleaner = onCleanup(@() rmdir(d, 's'));
    % JSON text, so backslashes are doubled: "\\\\evil..." is the UNC path \\evil...
    bad = {'"//evil.example/share/time.mat"', '"\\\\evil.example\\share\\time.mat"', '"C:/data/time.mat"', ...
        '"C:time.mat"', '"/tmp/time.mat"', '"../parity/time.mat"', '"sub\\..\\..\\time.mat"', ...
        '"secret.txt"', '"time.npz"', '"NUL.mat"', '"sub/con.csv"', '""', '5', 'null'};
    for k = 1:numel(bad)
        writeTimeFileJson(d, bad{k});
        checkLoadFails(d, ['time_file ' bad{k}], 'time_file');
    end
    mkdir(fullfile(d, 'raw'));
    movefile(fullfile(d, 'time.mat'), fullfile(d, 'raw', 'time.mat'));
    writeTimeFileJson(d, '"raw/time.mat"');
    t = ods.loadTest(d);
    check(size(t.data, 2) == 28, 'a time_file in a subfolder loads');
    movefile(fullfile(d, 'raw', 'time.mat'), fullfile(d, 'time.mat'));
    writeTimeFileJson(d, '"time.mat"');

    % .mat contents: other variables are ignored, a non-numeric "data" is refused before use
    s = load(fullfile(src, 'time.mat'));
    data = s.data; channels = s.channels; fs = s.fs; other = 'never read'; %#ok<NASGU>
    save(fullfile(d, 'time.mat'), '-v7', 'data', 'channels', 'fs', 'other');
    ods.loadTest(d);
    data = num2cell(s.data(1:8, :)); %#ok<NASGU>
    save(fullfile(d, 'time.mat'), '-v7', 'data', 'channels', 'fs');
    checkLoadFails(d, 'a cell array as data', 'data');
    copyfile(fullfile(src, 'time.mat'), fullfile(d, 'time.mat'));

    % non-finite coordinates
    geo = ods.readText(fullfile(src, 'geometry.csv'));
    rows = regexp(geo, '\n', 'split');
    parts = regexp(rows{2}, ',', 'split');
    parts{2} = 'nan';
    rows{2} = strjoin(parts, ',');
    fid = fopen(fullfile(d, 'geometry.csv'), 'w');
    fprintf(fid, '%s', strjoin(rows, sprintf('\n')));
    fclose(fid);
    checkLoadFails(d, 'a nan coordinate', 'non-finite');
end

function testSafeOutput()
    % Channel names and units end up in CSV files and the HTML viewer: they must not become
    % spreadsheet formulas, shift CSV columns, or act as markup (Python: tests/test_input_safety.py).
    here = fileparts(mfilename('fullpath'));
    test = ods.loadTest(fullfile(here, '..', '..', 'testdata', 'data', 'parity'));
    resp = test.responses;
    test.channelNames{resp(1)} = '=HYPERLINK("x")';
    test.channelNames{resp(2)} = 'a,b';
    test.channelNames{resp(3)} = '<!--<script>';
    res = ods.runPipeline(test, struct('df', 4, 'band', [20 450]));
    res.test.units = 'g,=x';
    d = tempname();
    cleaner = onCleanup(@() rmdir(d, 's'));
    ods.exportResults(res, d);

    lines = regexp(ods.readText(fullfile(d, 'transmissibility.csv')), '\n', 'split');
    header = lines{1};
    check(~isempty(strfind(header, '"''=HYPERLINK(""x"")_mag"')), 'formula name gets a '' prefix and quotes'); %#ok<STREMP>
    check(~isempty(strfind(header, ',"a,b_mag",')), 'a name with a comma is quoted'); %#ok<STREMP>
    peaks = regexp(ods.readText(fullfile(d, 'ods_peaks.csv')), '\n', 'split');
    check(~isempty(strfind(peaks{1}, ',"disp_rel_mm_per_g,=x",')), 'units with a comma are quoted'); %#ok<STREMP>

    html = ods.readText(ods.buildViewer(res, fullfile(d, 'v.html'), '<b>title</b>'));
    check(~any(html == char(13)), 'viewer written with LF only (its CSP hashes the LF script)');
    tag = '<script id="ods-data" type="application/json">';
    i0 = strfind(html, tag) + numel(tag);
    i1 = strfind(html(i0:end), '</script>');
    block = html(i0:i0 + i1(1) - 2);
    check(~any(block == '<') && ~any(block == '>') && ~any(block == '&'), 'no markup characters in the data block');
    check(~isempty(strfind(block, '\u003c!--\u003cscript\u003e')), 'markup in a name is escaped'); %#ok<STREMP>
    check(numel(strfind(html, '</script>')) == 2, 'nothing injected after the data block');
end

function testSharedCases()
    % Runs every language-neutral case in testdata/cases (the Python runner reads the same files).
    % Comparison rule, per element: |actual - expected| <= atol + atol_fullscale*max|expected| + rtol*|expected|.
    here = fileparts(mfilename('fullpath'));
    root = fullfile(here, '..', '..', 'testdata');
    files = dir(fullfile(root, 'cases', '*.json'));
    check(~isempty(files), 'no shared cases found in %s', root);
    for k = 1:numel(files)
        spec = jsondecode(ods.readText(fullfile(root, 'cases', files(k).name)));
        check(strcmp(spec.id, files(k).name(1:end-5)), '%s: id must equal the file name', files(k).name);
        check(~isempty(spec.checks), '%s: a case with no checks would pass vacuously', spec.id);
        golden = load(fullfile(root, spec.expected));
        test = ods.loadTest(fullfile(root, spec.input));
        res = ods.runPipeline(test, struct('df', spec.options.df, 'band', spec.options.band(:)'));
        actual = sharedActuals(res);
        for c = 1:numel(spec.checks)
            ch = spec.checks(c);
            check(isfield(actual, ch.quantity), '%s: runner does not expose quantity %s', spec.id, ch.quantity);
            e = double(golden.(ch.quantity)(:));
            atol = ch.atol + ch.atol_fullscale * max([abs(e(~isnan(e))); 0]);
            checkClose(double(actual.(ch.quantity)(:)), e, ch.rtol, atol, [spec.id ':' ch.quantity]);
        end
    end
end

function a = sharedActuals(res)
    % The quantities a case may check, under the names used in the golden files.
    a.f = res.sp.f;
    a.T = res.sp.T;
    a.coh = res.sp.coh;
    a.Gbb = res.sp.Gbb;
    a.Gxx = res.sp.Gxx;
    a.T_rel = res.Trel;
    a.T_el = res.Tel;
    a.disp_el = res.dispEl;
    a.rigid_R = res.rigidR;
    a.nfft = res.sp.nfft;
    a.n_avg = res.sp.nAvg;
    a.peak_index = [res.peaks.index];
    a.peak_f = [res.peaks.f];
    a.peak_mpc = [res.peaks.mpc];
    a.peak_coh = [res.peaks.coh];
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
    % compareTruth loads only fn/phi/node ids from truth.mat and matches every peak
    tbl = ods.compareTruth(res, fullfile(d, 'truth.mat'));
    check(size(tbl, 1) == numel(res.peaks) && all(isfinite(tbl(:))), 'compareTruth table');
    % exports + viewer
    out = fullfile(d, 'out');
    files = ods.exportResults(res, out);
    check(numel(files) == 5, 'export file count');
    html = ods.readText(ods.buildViewer(res, fullfile(out, 'v.html'), 'test'));
    check(isempty(strfind(html, '/*__ODS_DATA__*/')), 'placeholder replaced'); %#ok<STREMP>
    check(~isempty(strfind(html, '"rigidR"')), 'viewer data embedded'); %#ok<STREMP>
    rmdir(d, 's');
end
