function parts = splitCsvLine(line)
%SPLITCSVLINE Split one CSV line into trimmed fields, honouring double quotes.
%   parts = ods.splitCsvLine('a, "b,c" ,"say ""hi"""') returns {'a', 'b,c', 'say "hi"'}.
%   Commas inside quotes do not split, and "" inside quotes is a literal quote, as in
%   Python's csv module. Fields are trimmed of surrounding whitespace (and of a CR).

    parts = {};
    field = '';
    inQuotes = false;
    k = 1;
    n = numel(line);
    while k <= n
        c = line(k);
        if inQuotes
            if c == '"'
                if k < n && line(k + 1) == '"'
                    field(end + 1) = '"'; %#ok<AGROW>
                    k = k + 1;
                else
                    inQuotes = false;
                end
            else
                field(end + 1) = c; %#ok<AGROW>
            end
        elseif c == '"'
            inQuotes = true;
        elseif c == ','
            parts{end + 1} = strtrim(field); %#ok<AGROW>
            field = '';
        else
            field(end + 1) = c; %#ok<AGROW>
        end
        k = k + 1;
    end
    parts{end + 1} = strtrim(field);
end
