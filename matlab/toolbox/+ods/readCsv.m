function tbl = readCsv(path)
%READCSV Read a small text CSV into a header + cell matrix of trimmed strings.
%   tbl = ods.readCsv(path) returns a struct with fields
%     header : 1 x nc cellstr, lower-cased and trimmed
%     cells  : nr x nc cellstr, trimmed
%   Intended for the small geometry/channel/line tables, not for time histories.
%   Uses only base functions so it also runs in GNU Octave.

    txt = ods.readText(path);
    lines = regexp(txt, '\r?\n', 'split');
    lines = lines(~cellfun(@(s) isempty(strtrim(s)), lines));
    if isempty(lines)
        error('ods:readCsv', 'Empty CSV file: %s', path);
    end
    tbl.header = lower(ods.splitCsvLine(lines{1}));
    nc = numel(tbl.header);
    nr = numel(lines) - 1;
    tbl.cells = repmat({''}, nr, nc);
    for r = 1:nr
        parts = ods.splitCsvLine(lines{r + 1});
        n = min(nc, numel(parts));
        tbl.cells(r, 1:n) = parts(1:n);
    end
end
