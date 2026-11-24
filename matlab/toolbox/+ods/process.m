function res = process(testDir, outDir, opts)
%PROCESS One call from a test folder to all outputs (MATLAB twin of `ods run`).
%   res = ods.process(testDir)                       % outputs to ./outputs
%   res = ods.process(testDir, outDir, opts)
%   opts fields (all optional): df, band, prominenceDb, minCoh (see runPipeline), title.
%   Writes ods_results.mat, transmissibility/coherence/asd/ods_peaks CSVs and
%   ods_viewer.html; prints a summary, and a truth comparison if truth.mat exists.
    if nargin < 2 || isempty(outDir), outDir = 'outputs'; end
    if nargin < 3, opts = struct(); end
    tic;
    test = ods.loadTest(testDir);
    res = ods.runPipeline(test, opts);
    files = ods.exportResults(res, outDir);
    [~, name] = fileparts(regexprep(char(testDir), '[\\/]+$', ''));   % trailing separator would give ''
    if isfield(opts, 'title') && ~isempty(opts.title), name = opts.title; end
    files{end + 1} = ods.buildViewer(res, fullfile(outDir, 'ods_viewer.html'), name);

    sp = res.sp;
    fprintf('%d channels, fs %g Hz, nfft %d (df %.3f Hz), %d averages, %.1f s\n', ...
        numel(test.channelNames), test.fs, sp.nfft, sp.f(2), sp.nAvg, toc);
    fprintf('%d peaks: %s Hz\n', numel(res.peaks), strjoin(arrayfun(@(p) sprintf('%.1f', p.f), ...
        res.peaks, 'UniformOutput', false), ', '));
    fprintf('  wrote %s\n', files{:});
    truth = fullfile(testDir, 'truth.mat');
    if exist(truth, 'file')
        ods.compareTruth(res, truth);
    end
end
