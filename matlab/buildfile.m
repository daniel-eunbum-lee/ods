function plan = buildfile
%BUILDFILE Tasks for MATLAB's build tool.  From this folder:  buildtool test
%   (GNU Octave has no buildtool: run `addpath matlab/tests; run_tests` there instead.)
    plan = buildplan(localfunctions);
    plan.DefaultTasks = "test";
end

function testTask(~)
    % Runs the plain-assert suite, which also runs the shared cases in ../testdata.
    addpath(fullfile(fileparts(mfilename('fullpath')), 'tests'));
    run_tests();
end
