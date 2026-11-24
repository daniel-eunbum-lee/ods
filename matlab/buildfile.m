function plan = buildfile
%BUILDFILE Tasks for MATLAB's build tool.  From this folder:  buildtool test
%   (GNU Octave has no buildtool: run `addpath matlab/tests; run_tests` there instead.)
    plan = buildplan(localfunctions);
    plan.DefaultTasks = "test";
end

function testTask(~)
    % The same suite and reports as run_all_tests (JUnit, coverage; folder from ODS_TEST_OUT or tempdir),
    % including the shared cases in ../testdata.
    addpath(fullfile(fileparts(mfilename('fullpath')), 'tests'));
    run_all_tests();
end
