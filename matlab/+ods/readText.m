function txt = readText(path)
%READTEXT Read a whole text file as UTF-8 into a char row vector.
    fid = fopen(path, 'r', 'n', 'UTF-8');
    if fid < 0
        error('ods:readText', 'Cannot open %s', path);
    end
    cleaner = onCleanup(@() fclose(fid));
    txt = fread(fid, Inf, '*char')';
end
