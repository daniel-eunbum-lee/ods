function Trel = relativeTransmissibility(T, dirs, excitation)
%RELATIVETRANSMISSIBILITY Remove the rigid table motion: T_rel = T - d.e per channel.
%   T is nf x nch, dirs nch x 3, excitation 1x3. A sensor along the excitation sees the
%   table at T = 1, so T - 1 is the motion relative to the fixture. A cross-axis sensor
%   (d.e = 0) has nothing to subtract; a skewed one subtracts its projection.
    Trel = T - (dirs * excitation(:))';
end
