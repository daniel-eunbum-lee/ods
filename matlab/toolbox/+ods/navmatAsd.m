function asd = navmatAsd(f)
%NAVMATASD NAVMAT P-9492 style random profile, g^2/Hz (6.06 grms over 20-2000 Hz).
%   20-80 Hz: +3 dB/oct up to 0.04; 80-350 Hz: flat 0.04; 350-2000 Hz: -3 dB/oct.
    asd = zeros(size(f));
    lo = f >= 20 & f < 80;
    mid = f >= 80 & f <= 350;
    hi = f > 350 & f <= 2000;
    asd(lo) = 0.04 * f(lo) / 80;
    asd(mid) = 0.04;
    asd(hi) = 0.04 * 350 ./ f(hi);
end
