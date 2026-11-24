function v = parseDirection(text)
%PARSEDIRECTION '+X', '-z', 'Y' or 'dx dy dz' -> 1x3 unit vector (global axes).
    s = upper(strtrim(text));
    axisChar = regexprep(s, '^[+-]', '');
    names = 'XYZ';
    if numel(axisChar) == 1 && any(axisChar == names)
        v = double(names == axisChar);
        if s(1) == '-'
            v = -v;
        end
        return
    end
    parts = strsplit(strtrim(strrep(s, ',', ' ')));
    v = str2double(parts);
    if numel(v) ~= 3 || any(isnan(v)) || norm(v) == 0
        error('ods:parseDirection', 'Bad direction ''%s'': use +X/-Y/Z or three components', text);
    end
    v = v / norm(v);
end
