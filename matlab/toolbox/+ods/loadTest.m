function test = loadTest(testDir)
%LOADTEST Load one shaker run: time histories + geometry.
%   test = ods.loadTest(testDir) reads the same folder layout as the Python tool:
%
%     test.json     {"fs":5120, "units":"g", "excitation_axis":"Z", "time_file":"time.mat"}
%     time.mat      data (N x nch), channels (cellstr), fs     -- or --
%     time.csv      header = channel names; optional first column "time" (s)
%     geometry.csv  node,x,y,z[,base]
%     channels.csv  channel,node,direction,role   (exactly one role=control)
%     lines.csv     node_a,node_b                 (optional)
%
%   (time.npz is Python-only; convert with `ods synth --format mat` or save a .mat.)
%
%   Returned struct fields:
%     fs, units, excitation (1x3), data (N x nch), channelNames (1 x nch cellstr),
%     channelNodes (nch x 1), channelDirs (nch x 3), control (column index),
%     responses (indices of all other channels), nodeIds, nodeXyz, nodeIsBase, lines (L x 2)

    meta = struct();
    metaPath = fullfile(testDir, 'test.json');
    if exist(metaPath, 'file')
        meta = jsondecode(ods.readText(metaPath));
    end
    fsMeta = [];
    if isfield(meta, 'fs'), fsMeta = double(meta.fs); end

    if isfield(meta, 'time_file')
        timeFile = fullfile(testDir, checkTimeFile(meta.time_file));
    else
        timeFile = '';
        for cand = {'time.mat', 'time.csv'}
            if exist(fullfile(testDir, cand{1}), 'file')
                timeFile = fullfile(testDir, cand{1});
                break
            end
        end
        if isempty(timeFile)
            error('ods:loadTest', 'No time.mat or time.csv in %s', testDir);
        end
    end
    [data, names, fs] = loadTime(timeFile, fsMeta);

    % --- geometry
    geo = ods.readCsv(fullfile(testDir, 'geometry.csv'));
    nodeIds = str2double(col(geo, 'node'));
    nodeXyz = [str2double(col(geo, 'x')), str2double(col(geo, 'y')), str2double(col(geo, 'z'))];
    bad = ~isfinite(nodeIds) | any(~isfinite(nodeXyz), 2);   % NaN = not a number, or "nan"/"inf"
    if any(bad)
        ids = col(geo, 'node');
        error('ods:loadTest', 'geometry.csv has non-numeric or non-finite values for node(s) %s', ...
            strjoin(ids(bad)', ', '));
    end
    if any(strcmp(geo.header, 'base'))
        nodeIsBase = ismember(lower(col(geo, 'base')), {'1', 'true', 'yes'});
    else
        nodeIsBase = false(numel(nodeIds), 1);
    end

    % --- channels
    ch = ods.readCsv(fullfile(testDir, 'channels.csv'));
    chNames = col(ch, 'channel');
    chNodes = str2double(col(ch, 'node'));
    chDirs = col(ch, 'direction');
    if any(strcmp(ch.header, 'role'))
        chRoles = lower(col(ch, 'role'));
    else
        chRoles = repmat({'response'}, numel(chNames), 1);
    end

    [uniq, firstIdx] = unique(chNames);
    if numel(uniq) < numel(chNames)
        dup = chNames(setdiff(1:numel(chNames), firstIdx));
        error('ods:loadTest', 'Duplicate channel in channels.csv: %s', dup{1});
    end
    [found, loc] = ismember(names, chNames);
    if ~all(found)
        error('ods:loadTest', 'Channels in time data but not in channels.csv: %s', strjoin(names(~found), ', '));
    end
    missingNodes = setdiff(chNodes, nodeIds);
    if ~isempty(missingNodes)
        error('ods:loadTest', 'channels.csv references nodes missing from geometry.csv: %s', mat2str(missingNodes'));
    end

    nch = numel(names);
    test.channelNodes = chNodes(loc);
    test.channelDirs = zeros(nch, 3);
    for c = 1:nch
        test.channelDirs(c, :) = ods.parseDirection(chDirs{loc(c)});
    end
    controls = find(strcmp(chRoles(loc), 'control'));
    if numel(controls) ~= 1
        error('ods:loadTest', 'Need exactly one channel with role=control, found %d', numel(controls));
    end

    % --- lines
    test.lines = zeros(0, 2);
    linesPath = fullfile(testDir, 'lines.csv');
    if exist(linesPath, 'file')
        ln = ods.readCsv(linesPath);
        test.lines = [str2double(col(ln, 'node_a')), str2double(col(ln, 'node_b'))];
    end

    % --- excitation axis
    if isfield(meta, 'excitation_axis') && ~(isnumeric(meta.excitation_axis) && isempty(meta.excitation_axis))   % JSON null = not set; '' is an error, as in Python. (jsondecode gives [] for both null and an empty array, so [] is also 'not set' here, unlike Python.)
        raw = meta.excitation_axis;
        axisName = '';
        if ischar(raw) && (isrow(raw) || isempty(raw))   % numbers, arrays, objects are errors
            axisName = upper(strtrim(raw));
        elseif isnumeric(raw) || islogical(raw)
            raw = mat2str(raw);
        else
            raw = class(raw);
        end
        if isempty(regexp(axisName, '^[+-]?[XYZ]$', 'once'))
            % Silently falling back to the control's direction would hide a skewed control (#12).
            error('ods:loadTest', 'excitation_axis must be X, Y or Z (optionally signed), got %s', ...
                char(raw));
        end
        test.excitation = ods.parseDirection(axisName);
    else
        test.excitation = test.channelDirs(controls, :);
    end

    test.fs = fs;
    test.units = 'g';
    if isfield(meta, 'units'), test.units = meta.units; end
    test.data = data;
    test.channelNames = names(:)';
    test.control = controls;
    test.responses = setdiff(1:nch, controls);
    test.nodeIds = nodeIds(:);
    test.nodeXyz = nodeXyz;
    test.nodeIsBase = nodeIsBase(:);
end

function c = col(tbl, name)
% Column of a readCsv table by (lower-case) header name, as an n x 1 cellstr.
    j = find(strcmp(tbl.header, name), 1);
    if isempty(j)
        error('ods:loadTest', 'Missing column "%s"', name);
    end
    c = tbl.cells(:, j);
end

function [data, names, fs] = loadTime(path, fsMeta)
    [~, ~, ext] = fileparts(path);
    fsFile = [];
    switch lower(ext)
        case '.mat'
            s = loadMat(path);
            data = double(s.data);
            names = s.channels;
            if ischar(names), names = cellstr(names); end
            names = strtrim(names(:)');
            if isfield(s, 'fs'), fsFile = double(s.fs); end
        case '.csv'
            checkSize(csvDataBytes(path), path);   % a text file cannot decompress: an estimate is enough
            fid = fopen(path, 'r', 'n', 'UTF-8');   % header line only: the file may be large
            header = fgetl(fid);
            fclose(fid);
            if ~isempty(header) && double(header(1)) == 65279   % Excel "CSV UTF-8" BOM
                header = header(2:end);
            end
            names = ods.splitCsvLine(header);
            data = dlmread(path, ',', 1, 0);
            data = data(:, 1:numel(names));  % dlmread can pad a trailing empty column
            if strcmpi(names{1}, 'time')
                % Span over count, not 1/median(diff): printed times are rounded, so the
                % individual steps are quantised and the median step can be off.
                t = data(:, 1);
                if numel(t) > 1 && t(end) > t(1)
                    fsFile = (numel(t) - 1) / (t(end) - t(1));
                end
                data = data(:, 2:end);
                names = names(2:end);
            end
        otherwise
            error('ods:loadTest', 'Unsupported time file %s (use .mat or .csv)', path);
    end
    % test.json wins, so a user can correct a wrong rate without rewriting the time file.
    fs = fsMeta;
    if isempty(fs), fs = fsFile; end
    if isempty(fs)
        error('ods:loadTest', 'Sample rate unknown: put "fs" in test.json or a "time" column in the CSV');
    end
end

function name = checkTimeFile(name)
% test.json's time_file must be a relative path inside the test folder. test.json travels with
% the data, possibly from someone else: an absolute path, a UNC path (//host/share/x.csv, which
% makes Windows connect to that host and send the user's login hash) or a '..' step would
% otherwise read files outside the folder.
    if isstring(name) && isscalar(name), name = char(name); end
    if ~ischar(name) || size(name, 1) ~= 1 || isempty(strtrim(name))
        if ischar(name), shown = ['''' name(:)' ''''];
        elseif isnumeric(name) || islogical(name), shown = mat2str(name);   % JSON null arrives as []
        else, shown = class(name);
        end
        error('ods:loadTest', 'time_file must be a file name, got %s', shown);
    end
    parts = regexp(name, '[\\/]', 'split');
    if any(name(1) == '/\') || ~isempty(regexp(name, '^[A-Za-z]:', 'once')) || any(strcmp(parts, '..'))
        error('ods:loadTest', 'time_file must be a relative path inside the test folder, got %s', name);
    end
    % Opening these on Windows reaches a device, whatever the folder or extension (NUL.csv is NUL).
    devices = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'};
    for d = [num2cell('123456789'), {char(185), char(178), char(179)}]   % also superscript 1-3
        devices = [devices, {['COM' d{1}], ['LPT' d{1}]}]; %#ok<AGROW>
    end
    for i = 1:numel(parts)
        if any(strcmp(upper(strtrim(regexp(parts{i}, '^[^.:]*', 'match', 'once'))), devices))
            error('ods:loadTest', 'time_file must not name a Windows device (CON, NUL, COM1, ...), got %s', name);
        end
    end
    [~, ~, ext] = fileparts(strrep(name, '\', '/'));
    if ~any(strcmpi(ext, {'.mat', '.csv'}))
        error('ods:loadTest', 'time_file must end in .mat or .csv (.npz is Python-only), got %s', name);
    end
end

function s = loadMat(path)
% Load only data, channels and fs, after checking their classes and sizes as whos lists them.
% load(path) would restore every variable in the file, and loading an object runs its class's
% loadobj (if that class is on the path); a crafted file could also declare huge arrays.
% MATLAB's whos -file reads only the variable headers. GNU Octave lists a file by loading it, so
% there the checks run after the file has been read; they still refuse what it contains.
    wanted = {'data', 'channels', 'fs'};
    whosOk = true;
    try
        info = whos('-file', path);
    catch
        whosOk = false;   % the checks after load still apply
    end
    if whosOk
        info = info(ismember({info.name}, wanted));
        numeric = {'double', 'single', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', ...
            'int64', 'uint64', 'logical'};
        total = 0;
        for k = 1:numel(info)
            ok = any(strcmp(info(k).class, numeric)) || (strcmp(info(k).name, 'channels') && ...
                any(strcmp(info(k).class, {'cell', 'char', 'string'})));
            if ~ok
                error('ods:loadTest', '%s: variable "%s" has class %s', path, info(k).name, info(k).class);
            end
            total = total + max(prod(info(k).size) * 8, info(k).bytes);   % data as double
        end
        checkSize(total, path);
        wanted = {info.name};
    end
    if ~any(strcmp(wanted, 'data')) || ~any(strcmp(wanted, 'channels'))
        error('ods:loadTest', '%s must contain "data" and "channels"', path);
    end
    s = load(path, wanted{:});
    if ~isfield(s, 'data') || ~isfield(s, 'channels')
        error('ods:loadTest', '%s must contain "data" and "channels"', path);
    end
    if isstring(s.channels), s.channels = cellstr(s.channels); end
    if ~(isnumeric(s.data) || islogical(s.data)) || ~(iscellstr(s.channels) || ischar(s.channels)) || ...
            (isfield(s, 'fs') && ~isnumeric(s.fs))
        error('ods:loadTest', '%s: "data" and "fs" must be numeric and "channels" text', path);
    end
end

function nbytes = csvDataBytes(path)
% Estimated size of a time CSV as double: rows (file size / median line length) x columns.
    nbytes = 0;
    fid = fopen(path, 'r');
    if fid < 0, return; end
    cleaner = onCleanup(@() fclose(fid));
    info = dir(path);
    if isempty(info), return; end
    cap = 2^20;   % a file with no line breaks must not be read whole just to estimate its size
    header = fgets(fid, cap);
    lens = zeros(1, 0);
    for k = 1:200
        row = fgets(fid, cap);
        if ~ischar(row), break; end
        if ~isempty(strtrim(row)), lens(end + 1) = numel(row); end %#ok<AGROW>
    end
    if isempty(lens) || ~ischar(header), return; end
    lens = sort(lens);
    rows = (info(1).bytes - numel(header)) / lens(floor(numel(lens) / 2) + 1);
    nbytes = rows * (sum(header == ',') + 1) * 8;
end

function checkSize(nbytes, path)
% Largest time-data array accepted (bytes as double): 8 GiB is ~1e9 samples, e.g. 64 channels
% x 5120 Hz x 54 min. The same limit as Python's ods.io.MAX_TIME_DATA_BYTES; raise both if needed.
    maxBytes = 8 * 2^30;
    if nbytes > maxBytes
        error('ods:loadTest', '%s: time data would take %.3g GiB, above the %.3g GiB limit', ...
            path, nbytes / 2^30, maxBytes / 2^30);
    end
end
