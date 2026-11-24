function result = run_all_tests(outDir)
%RUN_ALL_TESTS Run the whole MATLAB test suite (the one CI runs) and save the reports.
%   From the repository root, in MATLAB or GNU Octave:
%
%       addpath('matlab/tests'); run_all_tests
%
%   result = run_all_tests()        reports go to a new folder under tempdir
%   result = run_all_tests(outDir)  reports go to outDir (created if needed)
%
%   The folder can also be set with the environment variable ODS_TEST_OUT (CI uses this).
%   Nothing is written inside the repository. Files saved:
%     test-log.txt         everything printed while the tests ran
%     environment.txt      date, MATLAB/Octave version, OS, git commit
%     junit.xml            one result per test                                  (MATLAB only)
%     coverage.xml         code coverage of matlab/toolbox, Cobertura format    (MATLAB only)
%     coverage-html/       the same coverage as a browsable report (open index.html)  (MATLAB only)
%   GNU Octave has no test-framework or coverage tools, so there it saves the log and environment only.
%
%   result is a struct with fields passed (logical), outDir, and nTests. If any test fails the
%   reports are still saved and this function then raises an error, so scripts and CI notice.
    here = fileparts(mfilename('fullpath'));
    toolbox = fullfile(here, '..', 'toolbox');
    previous = cd(toolbox);   % canonical path, without the '..', for the coverage plugin
    toolbox = pwd;
    cd(previous);
    addpath(toolbox);
    addpath(here);

    if nargin < 1 || isempty(outDir)
        outDir = getenv('ODS_TEST_OUT');
    end
    if isempty(outDir)
        outDir = fullfile(tempdir, ['ods-matlab-tests-' datestr(now, 'yyyymmdd-HHMMSS-FFF')]);
    end
    if ~exist(outDir, 'dir')
        [ok, msg] = mkdir(outDir);
        if ~ok
            error('ods:tests', 'Cannot create the report folder %s: %s', outDir, msg);
        end
    end
    outDir = absolutePath(outDir);

    writeEnvironment(fullfile(outDir, 'environment.txt'), here);
    names = run_tests('names');

    logFile = fullfile(outDir, 'test-log.txt');
    if exist(logFile, 'file'), delete(logFile); end
    diary(logFile);
    stopDiary = onCleanup(@() diary('off'));

    if exist('OCTAVE_VERSION', 'builtin') ~= 0
        passed = runPlain();
        fprintf('GNU Octave: no coverage or JUnit report (needs MATLAB).\n');
    else
        passed = runWithTestFramework(outDir, toolbox);
    end
    diary('off');

    fprintf('\nReports saved in: %s\n', outDir);
    result = struct('passed', passed, 'outDir', outDir, 'nTests', numel(names));
    if ~passed
        error('ods:tests', 'Some tests failed; reports are in %s', outDir);
    end
end

function passed = runPlain()
    try
        run_tests();
        passed = true;
    catch err
        fprintf('%s\n', err.message);
        passed = false;
    end
end

function passed = runWithTestFramework(outDir, toolbox)
    % Fully qualified names, so this file also parses in GNU Octave (which never calls this).
    suite = matlab.unittest.TestSuite.fromClass(meta.class.fromName('OdsSuite'));
    runner = matlab.unittest.TestRunner.withTextOutput;
    runner.addPlugin(matlab.unittest.plugins.XMLPlugin.producingJUnitFormat(fullfile(outDir, 'junit.xml')));
    formats = [matlab.unittest.plugins.codecoverage.CoverageReport(fullfile(outDir, 'coverage-html')), ...
               matlab.unittest.plugins.codecoverage.CoberturaFormat(fullfile(outDir, 'coverage.xml'))];
    runner.addPlugin(matlab.unittest.plugins.CodeCoveragePlugin.forFolder(toolbox, ...
        'IncludingSubfolders', true, 'Producing', formats));
    results = runner.run(suite);
    % An empty result set must not count as a pass.
    passed = numel(results) == numel(run_tests('names')) && all([results.Passed]);
end

function writeEnvironment(file, here)
    fid = fopen(file, 'w');
    cleanup = onCleanup(@() fclose(fid));
    fprintf(fid, 'date:     %s\n', datestr(now, 'yyyy-mm-dd HH:MM:SS'));
    if exist('OCTAVE_VERSION', 'builtin') ~= 0
        fprintf(fid, 'runtime:  GNU Octave %s\n', OCTAVE_VERSION);
    else
        fprintf(fid, 'runtime:  MATLAB %s\n', version);
    end
    fprintf(fid, 'platform: %s\n', computer);
    % The folder goes through an environment variable, never into the command text, so an odd
    % folder name (a $, a backtick, a quote) cannot be run as shell code.
    setenv('ODS_REPO_DIR', here);
    unsetEnv = onCleanup(@() setenv('ODS_REPO_DIR', ''));
    if ispc
        ref = '"%ODS_REPO_DIR%"';
    else
        ref = '"$ODS_REPO_DIR"';
    end
    [status, commit] = system(['git -C ' ref ' rev-parse HEAD']);
    if status == 0
        fprintf(fid, 'commit:   %s', commit);
        [~, dirty] = system(['git -C ' ref ' status --porcelain --untracked-files=no']);
        if ~isempty(strtrim(dirty))
            fprintf(fid, 'working tree has uncommitted changes\n');
        end
    else
        fprintf(fid, 'commit:   (git is not available, or this is not a git checkout)\n');
    end
end

function p = absolutePath(p)
    % Absolute path without Java: a path is absolute if it starts with / (or \) or a drive letter.
    isAbs = ~isempty(regexp(p, '^([A-Za-z]:|[\\/])', 'once'));
    if ~isAbs
        p = fullfile(pwd, p);
    end
end
