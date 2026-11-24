function txt = readText(path)
%READTEXT Read a whole text file as UTF-8 into a char row vector.
    fid = fopen(path, 'r', 'n', 'UTF-8');
    if fid < 0
        error('ods:readText', 'Cannot open %s', path);
    end
    cleaner = onCleanup(@() fclose(fid));
    txt = fread(fid, Inf, '*char')';
    % Excel's "CSV UTF-8" starts with a byte-order mark; drop it so the first header matches.
    if ~isempty(txt) && double(txt(1)) == 65279
        txt = txt(2:end);
    elseif numel(txt) >= 3 && isequal(double(txt(1:3)), [239 187 191])   % BOM read as bytes
        txt = txt(4:end);
    end
end
