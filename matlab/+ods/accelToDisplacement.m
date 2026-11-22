function D = accelToDisplacement(A, f, units)
%ACCELTODISPLACEMENT Acceleration per unit input -> displacement in mm per unit input.
%   D = ods.accelToDisplacement(A, f, units) with A nf x nch (or nf x 1), f in Hz.
%   x = a / (-w^2) in the frequency domain; the DC bin is set to 0 rather than Inf.
%   units 'g' converts with g0 = 9.80665 m/s^2 first; anything else is taken as m/s^2.
    if nargin < 3, units = 'g'; end
    if strcmpi(units, 'g')
        toSi = ods.G0();
    else
        toSi = 1;
    end
    w2 = (2 * pi * f(:)) .^ 2;
    scale = zeros(size(w2));
    nz = w2 > 0;
    scale(nz) = -toSi * 1e3 ./ w2(nz);
    D = A .* scale;
end
