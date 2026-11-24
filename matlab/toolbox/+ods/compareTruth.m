function tbl = compareTruth(res, truthPath)
%COMPARETRUTH Match each ODS peak to the nearest true mode; print MAC per view.
%   tbl = ods.compareTruth(res, 'data/synthetic/truth.mat')
%   Columns of tbl: odsF, trueFn, macAbs, macRel, macEl, mpcAbs, cohWeighted.
%   macEl removes rigid-body motion from both the ODS and the true mode.
    % Load only the variables used: process() loads truth.mat from the test folder automatically,
    % and load() of a whole file would restore anything in it (an object runs its loadobj).
    vars = {'node_ids', 'nodeIds', 'fn', 'phi'};
    try
        info = whos('-file', truthPath);
        info = info(ismember({info.name}, vars));
        vars = {info.name};
        if ~all(ismember({'fn', 'phi'}, vars))
            error('ods:compareTruth', '%s must contain "fn" and "phi"', truthPath);
        end
        for k = 1:numel(info)
            if ~any(strcmp(info(k).class, {'double', 'single', 'int8', 'uint8', 'int16', 'uint16', ...
                    'int32', 'uint32', 'int64', 'uint64', 'logical'}))
                error('ods:compareTruth', '%s: variable "%s" has class %s', truthPath, info(k).name, info(k).class);
            end
        end
    catch err
        if strcmp(err.identifier, 'ods:compareTruth'), rethrow(err); end
        % whos -file failed (some Octave versions): load the names as given, never the whole file
    end
    tr = load(truthPath, vars{:});
    if ~isfield(tr, 'fn') || ~isfield(tr, 'phi') || ~isnumeric(tr.fn) || ~isnumeric(tr.phi)
        error('ods:compareTruth', '%s must contain numeric "fn" and "phi"', truthPath);
    end
    if isfield(tr, 'node_ids'), ids = tr.node_ids(:); else, ids = tr.nodeIds(:); end
    t = res.test;
    resp = t.responses;
    rows = zeros(numel(resp), 1);
    signs = zeros(numel(resp), 1);
    for m = 1:numel(resp)
        c = resp(m);
        [~, a] = max(abs(t.channelDirs(c, :)));
        rows(m) = 3 * (find(ids == t.channelNodes(c), 1) - 1) + a;
        signs(m) = sign(t.channelDirs(c, a));
    end
    fn = tr.fn(:);
    tbl = zeros(numel(res.peaks), 7);
    fprintf('\nPeak vs. nearest true mode, MAC on measured DOFs for each view of the ODS:\n');
    fprintf('%9s %9s %7s %8s %8s %7s %8s %7s\n', 'ODS f', 'true fn', 'df', 'MAC abs', 'MAC rel', ...
        'MAC el', 'MPC abs', 'coh w');
    for i = 1:numel(res.peaks)
        p = res.peaks(i);
        [~, j] = min(abs(fn - p.f));
        phi = tr.phi(rows, j) .* signs;
        k = p.index;
        row = [p.f, fn(j), ods.mac(res.sp.T(k, resp), phi), ods.mac(res.disp(k, resp), phi), ...
            ods.mac(res.dispEl(k, resp), res.rigidR * phi), p.mpc, p.coh];
        tbl(i, :) = row;
        fprintf('%9.2f %9.2f %+7.2f %8.3f %8.3f %7.3f %8.3f %7.3f\n', row(1), row(2), row(1) - row(2), row(3:end));
    end
end
