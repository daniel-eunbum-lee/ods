function written = exportResults(res, outDir)
%EXPORTRESULTS Write ods_results.mat + CSVs (same CSV layout as the Python tool).
%   written = ods.exportResults(res, outDir) returns a cellstr of written paths.
    if ~exist(outDir, 'dir'), mkdir(outDir); end
    t = res.test;
    sp = res.sp;
    names = t.channelNames;
    resp = t.responses;
    written = {};

    % --- everything, as MATLAB arrays
    r = struct();
    r.f = sp.f; r.T = sp.T; r.T_rel = res.Trel; r.T_elastic = res.Tel;
    r.disp_mm_per_unit = res.disp; r.disp_elastic_mm_per_unit = res.dispEl;
    r.rigid_R = res.rigidR; r.coherence = sp.coh; r.Gbb = sp.Gbb; r.Gxx = sp.Gxx;
    r.channels = names; r.channel_nodes = t.channelNodes; r.channel_dirs = t.channelDirs;
    pkIdx = [res.peaks.index];
    r.peak_f = [res.peaks.f]; r.peak_index = pkIdx;
    r.peak_mpc_abs = [res.peaks.mpc]; r.peak_coh_weighted = [res.peaks.coh];
    r.peak_shapes_mm_per_unit = res.disp(pkIdx, :);
    r.peak_shapes_elastic_mm_per_unit = res.dispEl(pkIdx, :);
    r.nfft = sp.nfft; r.n_avg = sp.nAvg; r.fs = t.fs;
    p = fullfile(outDir, 'ods_results.mat');
    save(p, '-struct', 'r', '-v7');
    written{end + 1} = p;

    keep = sp.f <= res.band(2);
    f = sp.f(keep);
    unit2 = [t.units '^2/Hz'];

    p = fullfile(outDir, 'transmissibility.csv');
    writeTable(p, [{'f_hz'}, strcat(names, '_mag'), strcat(names, '_phase_deg')], ...
        [f, abs(sp.T(keep, :)), angle(sp.T(keep, :)) * 180 / pi]);
    written{end + 1} = p;
    p = fullfile(outDir, 'coherence.csv');
    writeTable(p, [{'f_hz'}, names], [f, sp.coh(keep, :)]);
    written{end + 1} = p;
    p = fullfile(outDir, 'asd.csv');
    writeTable(p, [{'f_hz'}, strcat(names, ['_' unit2])], [f, sp.Gxx(keep, :)]);
    written{end + 1} = p;

    p = fullfile(outDir, 'ods_peaks.csv');
    fid = fopen(p, 'w', 'n', 'UTF-8');
    header = {'peak', 'f_hz', 'mpc_abs', 'channel', 'node', 'dx', 'dy', 'dz', 'T_mag', 'T_phase_deg', ...
        'T_rel_mag', 'T_rel_phase_deg', ['disp_rel_mm_per_' t.units], 'disp_rel_phase_deg', ...
        ['disp_elastic_mm_per_' t.units], 'disp_elastic_phase_deg', 'coherence'};
    fprintf(fid, '%s\n', strjoin(cellfun(@csvCell, header, 'UniformOutput', false), ','));
    mp = @(z) sprintf('%.6g,%.2f', abs(z), angle(z) * 180 / pi);
    for i = 1:numel(res.peaks)
        pk = res.peaks(i);
        k = pk.index;
        for c = resp
            d = t.channelDirs(c, :);
            fprintf(fid, '%d,%.3f,%.3f,%s,%d,%g,%g,%g,%s,%s,%s,%s,%.4f\n', i, pk.f, pk.mpc, csvCell(names{c}), ...
                t.channelNodes(c), d(1), d(2), d(3), mp(sp.T(k, c)), mp(res.Trel(k, c)), ...
                mp(res.disp(k, c)), mp(res.dispEl(k, c)), sp.coh(k, c));
        end
    end
    fclose(fid);
    written{end + 1} = p;
end

function writeTable(path, header, M)
    fid = fopen(path, 'w', 'n', 'UTF-8');
    fprintf(fid, '%s\n', strjoin(cellfun(@csvCell, header, 'UniformOutput', false), ','));
    fmt = [repmat('%.6g,', 1, size(M, 2) - 1), '%.6g\n'];
    fprintf(fid, fmt, M.');
    fclose(fid);
end

function s = csvCell(s)
% One CSV field from user text (a channel name or units), safe to open in a spreadsheet; the
% same rule as Python's ods.pipeline.csv_cell. A leading = + - @ (or tab / CR) makes Excel and
% LibreOffice evaluate the cell as a formula, so it gets a ' prefix; a comma, quote or line break
% would shift the columns, so such a field is quoted as in RFC 4180.
    s = char(s);
    if ~isempty(s) && any(s(1) == ['=+-@' char(9) char(13)])
        s = ['''' s];
    end
    if any(ismember(s, [',"' char(13) char(10)]))
        s = ['"' strrep(s, '"', '""') '"'];
    end
end
