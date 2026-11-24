function outPath = buildViewer(res, outPath, title)
%BUILDVIEWER Write the standalone HTML ODS viewer (same page as the Python tool).
%   ods.buildViewer(res, outPath, title)
%   Reuses the viewer template in toolbox/resources (a copy of python/src/ods/viewer_template.html,
%   kept identical by a Python test) and embeds the data as
%   JSON. The JSON is written by hand rather than with jsonencode so that 1-element
%   arrays stay arrays and the output is identical in MATLAB and Octave.
    if nargin < 3, title = 'Shaker test'; end
    t = res.test;
    sp = res.sp;
    keep = sp.f >= res.band(1) * 0.8 & sp.f <= res.band(2);
    idxMap = zeros(size(sp.f));
    idxMap(keep) = 0:nnz(keep) - 1;      % JS uses 0-based bins
    nch = numel(t.channelNames);

    if strcmpi(t.units, 'g'), toSi = ods.G0(); else, toSi = 1; end
    meta = sprintf(['{"title":%s,"fs":%s,"df":%s,"n_avg":%d,"units":%s,"to_si":%s,' ...
        '"excitation":%s,"band":%s,"control":%d,"grms":%s}'], ...
        jstr(title), num(t.fs), num(sp.f(2) - sp.f(1)), sp.nAvg, jstr(t.units), num(toSi), ...
        arr(t.excitation, '%.6g'), arr(res.band, '%.6g'), t.control - 1, ...
        num(std(t.data(:, t.control), 1) / max(abs(t.channelDirs(t.control, :) * t.excitation(:)), 0.5)));   % table rms

    chParts = cell(1, nch);
    for c = 1:nch
        chParts{c} = sprintf('{"name":%s,"node":%d,"dir":%s}', jstr(t.channelNames{c}), ...
            t.channelNodes(c), arr(round(t.channelDirs(c, :) * 1e6) / 1e6, '%.6g'));
    end

    nodeParts = cell(1, numel(t.nodeIds));
    for i = 1:numel(t.nodeIds)
        nodeParts{i} = sprintf('{"id":%d,"x":%s,"y":%s,"z":%s,"base":%s}', t.nodeIds(i), ...
            num(t.nodeXyz(i, 1)), num(t.nodeXyz(i, 2)), num(t.nodeXyz(i, 3)), jbool(t.nodeIsBase(i)));
    end

    lineParts = cell(1, size(t.lines, 1));
    for i = 1:size(t.lines, 1)
        lineParts{i} = sprintf('[%d,%d]', t.lines(i, 1), t.lines(i, 2));
    end

    proj = ods.nodeProjectors(t.nodeIds, t.channelNodes, t.channelDirs, t.responses);
    projParts = cell(1, numel(proj));
    for j = 1:numel(proj)
        projParts{j} = sprintf('"%d":{"idx":%s,"P":%s}', proj(j).nodeId, ...
            arr(proj(j).idx - 1, '%d'), mat(round(proj(j).P * 1e8) / 1e8, '%.8g'));
    end

    pkParts = {};
    for p = res.peaks
        if keep(p.index)
            pkParts{end + 1} = sprintf('{"i":%d,"f":%s,"db":%s,"coh":%s}', idxMap(p.index), ...
                num(p.f), num(p.indicatorDb), num(p.coh)); %#ok<AGROW>
        end
    end

    Tk = sp.T(keep, :);
    json = ['{"meta":' meta, ...
        ',"f":' arr(sp.f(keep), '%.7g'), ...
        ',"ch":[' strjoin(chParts, ',') ']', ...
        ',"Tre":' mat(real(Tk).', '%.5g'), ...
        ',"Tim":' mat(imag(Tk).', '%.5g'), ...
        ',"coh":' mat(sp.coh(keep, :).', '%.4g'), ...
        ',"nodes":[' strjoin(nodeParts, ',') ']', ...
        ',"lines":[' strjoin(lineParts, ',') ']', ...
        ',"resp":' arr(t.responses - 1, '%d'), ...
        ',"rigidR":' mat(round(res.rigidR * 1e8) / 1e8, '%.8g'), ...
        ',"proj":{' strjoin(projParts, ',') '}', ...
        ',"peaks":[' strjoin(pkParts, ',') ']}'];
    % Escape every < (not only </): "<!--<script" in a name would otherwise switch the HTML parser
    % into a state where the page's own </script> no longer ends the data block. \u003c etc. are
    % plain JSON escapes, so JSON.parse returns the original text. (Same as Python's embed_json.)
    json = strrep(strrep(strrep(json, '&', '\u0026'), '<', '\u003c'), '>', '\u003e');

    here = fileparts(mfilename('fullpath'));
    template = fullfile(here, '..', 'resources', 'viewer_template.html');
    % The page's Content-Security-Policy allows its script by a hash of the exact LF text, so a
    % template checked out with CRLF line endings must be written back with LF.
    template = strrep(ods.readText(template), sprintf('\r\n'), sprintf('\n'));
    html = strrep(template, '/*__ODS_DATA__*/', json);

    outDir = fileparts(outPath);
    if ~isempty(outDir) && ~exist(outDir, 'dir'), mkdir(outDir); end
    fid = fopen(outPath, 'w', 'n', 'UTF-8');
    fprintf(fid, '%s', html);
    fclose(fid);
end

% ---- tiny JSON writers (numbers must be finite; NaN/Inf are not valid JSON)

function s = num(v)
    if ~isfinite(v), v = 0; end
    s = sprintf('%.10g', v);
end

function s = arr(v, fmt)
    v = v(:)';
    v(~isfinite(v)) = 0;
    if isempty(v)
        s = '[]';
    else
        s = ['[' sprintf(fmt, v(1)) sprintf([',' fmt], v(2:end)) ']'];
    end
end

function s = mat(M, fmt)
% 2-D matrix as an array of row arrays.
    rows = cell(1, size(M, 1));
    for i = 1:size(M, 1)
        rows{i} = arr(M(i, :), fmt);
    end
    s = ['[' strjoin(rows, ',') ']'];
end

function s = jstr(txt)
    txt = char(txt);   % a string-class title would otherwise make ['"' txt '"'] a string array
    txt = strrep(txt, '\', '\\');
    txt = strrep(txt, '"', '\"');
    txt = regexprep(txt, '[\x00-\x1F]', ' ');   % raw control characters are invalid in JSON
    s = ['"' txt '"'];
end

function s = jbool(b)
    if b, s = 'true'; else, s = 'false'; end
end
