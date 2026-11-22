function v = mac(a, b)
%MAC Modal assurance criterion between two (possibly complex) shape vectors.
    a = a(:);
    b = b(:);
    v = abs(a' * b) ^ 2 / real((a' * a) * (b' * b));   % ' is the conjugate transpose
end
