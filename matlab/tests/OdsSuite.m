classdef OdsSuite < matlab.unittest.TestCase
    %ODSSUITE Exposes each plain-assert test of run_tests.m to MATLAB's test framework.
    %   The tests themselves live in run_tests.m (plain asserts, so GNU Octave can run them too).
    %   This wrapper only gives MATLAB one test per entry, which is what lets it produce
    %   JUnit results and code coverage. Run it through run_all_tests, not directly.

    properties (TestParameter)
        % One parameter per test name, e.g. OdsSuite/plainTest(testName=testSdofH1).
        testName = cell2struct(run_tests('names'), run_tests('names'), 2);
    end

    methods (Test)
        function plainTest(~, testName)
            run_tests(testName);
        end
    end
end
