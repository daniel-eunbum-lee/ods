%RUN_DEMO Synthetic shaker test -> ODS -> viewer, end to end in MATLAB.
%   Run from anywhere:  run('matlab/toolbox/examples/run_demo.m')
%   Takes a few seconds; writes matlab/data/synthetic and matlab/outputs.

here = fileparts(mfilename('fullpath'));
addpath(fullfile(here, '..'));  % the toolbox folder, which holds +ods

matlabDir = fullfile(here, '..', '..');
dataDir = fullfile(matlabDir, 'data', 'synthetic');
outDir = fullfile(matlabDir, 'outputs');

model = ods.synthBoxModel();
sim = ods.synthSimulate(model, 'Z', 5120, 60, 1);
ods.synthWriteTest(dataDir, model, sim);
fprintf('Synthetic test: %d samples x %d channels, input %.2f grms\n', size(sim.data), sim.grmsInput);

res = ods.process(dataDir, outDir, struct('title', 'Synthetic box on isolators (Z random)'));

% Open the interactive viewer, and animate the top-panel mode natively.
try
    web(fullfile(outDir, 'ods_viewer.html'), '-browser');
catch
    fprintf('Open %s in a browser.\n', fullfile(outDir, 'ods_viewer.html'));
end
[~, iPanel] = min(abs([res.peaks.f] - 283));
ods.animateShape(res, res.peaks(iPanel).f, 'el');
