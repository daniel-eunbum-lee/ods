function res = runPipeline(test, opts)
%RUNPIPELINE Test data -> spectra -> relative/elastic views -> peaks.
%   res = ods.runPipeline(test)
%   res = ods.runPipeline(test, opts) with optional fields
%     df (0.625 Hz), band ([20 2000] Hz), prominenceDb (3), minCoh (0.5)
%
%   Fields of res: test, sp (see computeSpectra), Trel, Tel, disp, dispEl (mm per unit
%   input), rigidR, peaks (see findPeaks), band.

    if nargin < 2, opts = struct(); end
    df = getOpt(opts, 'df', 0.625);
    band = getOpt(opts, 'band', [20 2000]);
    promDb = getOpt(opts, 'prominenceDb', 3);
    minCoh = getOpt(opts, 'minCoh', 0.5);

    nfft = 2 ^ ceil(log2(test.fs / df));
    sp = ods.computeSpectra(test.data, test.control, test.fs, nfft);
    % H1 is referenced to what the control reads, (d_ctrl . e) * table acceleration. Rescale
    % so T is per unit table acceleration along e; otherwise an inverted (-Z) or skewed
    % control breaks the relative view and the base-node motion.
    gain = test.channelDirs(test.control, :) * test.excitation(:);
    if abs(gain) < 0.5
        error('ods:runPipeline', ['Control direction is %.0f deg from the excitation axis; ' ...
            'check its direction in channels.csv and excitation_axis in test.json'], ...
            acosd(min(1, abs(gain))));
    end
    sp.T = sp.T / gain;
    Trel = ods.relativeTransmissibility(sp.T, test.channelDirs, test.excitation);
    Trel(:, test.control) = 0;   % the control is the reference: zero relative motion
    resp = test.responses;

    [~, loc] = ismember(test.channelNodes(resp), test.nodeIds);
    R = ods.rigidBodyProjector(test.nodeXyz(loc, :), test.channelDirs(resp, :));
    Tel = zeros(size(Trel));
    Tel(:, resp) = Trel(:, resp) * R.';   % table motion is rigid too, so T or T_rel give the same

    res.test = test;
    res.sp = sp;
    res.Trel = Trel;
    res.Tel = Tel;
    res.disp = ods.accelToDisplacement(Trel, sp.f, test.units);
    res.dispEl = ods.accelToDisplacement(Tel, sp.f, test.units);
    res.rigidR = R;
    res.peaks = ods.findPeaks(sp.f, sp.T(:, resp), sp.coh(:, resp), band, promDb, minCoh);
    res.band = band;
end

function v = getOpt(opts, name, default)
    if isfield(opts, name) && ~isempty(opts.(name))
        v = opts.(name);
    else
        v = default;
    end
end
