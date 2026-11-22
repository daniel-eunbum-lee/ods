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
        timeFile = fullfile(testDir, meta.time_file);
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
    axisName = '';
    if isfield(meta, 'excitation_axis'), axisName = upper(meta.excitation_axis); end
    axisVecs = struct('X', [1 0 0], 'Y', [0 1 0], 'Z', [0 0 1]);
    if ~isempty(axisName) && isfield(axisVecs, axisName)
        test.excitation = axisVecs.(axisName);
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
            s = load(path);
            data = double(s.data);
            names = s.channels;
            if ischar(names), names = cellstr(names); end
            names = strtrim(names(:)');
            if isfield(s, 'fs'), fsFile = double(s.fs); end
        case '.csv'
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
