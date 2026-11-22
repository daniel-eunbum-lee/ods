function model = synthBoxModel()
%SYNTHBOXMODEL 9-node lumped-mass box on 4 corner isolators (same model as Python).
%   * 8 corners joined by axial bar springs (12 edges + 6 face diagonals): stiff box,
%     elastic modes from ~220 Hz up.
%   * 4 isolators (axis-aligned kx/ky/kz) from the bottom corners to the table:
%     rigid-body modes 33-87 Hz.
%   * Top-panel centre node on bushings soft in Z only: "panel drum" mode ~283 Hz.
%   * +0.8 kg on one top corner so bounce/pitch/roll couple under single-axis input.
%   Units: m, kg, N/m. Fields: nodeIds, coords, M, K, lines, baseIds, baseXyz,
%   zetaRigid, zetaElastic, rigidCutoffHz.
    lx = 0.30; ly = 0.20; lz = 0.15;
    corners = [0 0 0; lx 0 0; lx ly 0; 0 ly 0];
    coords = [corners; corners(:, 1:2), repmat(lz, 4, 1); lx / 2, ly / 2, lz];
    n = size(coords, 1);

    masses = repmat(0.35, n, 1);
    masses(7) = masses(7) + 0.80;
    masses(9) = 0.20;
    M = diag(repelem(masses, 3));

    K = zeros(3 * n);
    kBar = 1.0e7;
    edges = [1 2; 2 3; 3 4; 4 1; 5 6; 6 7; 7 8; 8 5; 1 5; 2 6; 3 7; 4 8];
    diagonals = [1 3; 5 7; 1 6; 2 7; 3 8; 4 5];
    bars = [edges; diagonals];
    for e = 1:size(bars, 1)
        a = bars(e, 1); b = bars(e, 2);
        u = coords(b, :) - coords(a, :);
        u = u / norm(u);
        K = assemblePair(K, a, b, kBar * (u' * u));
    end
    kIso = diag([5.0e4, 5.0e4, 1.2e5]);       % grounded: acts on motion relative to the table
    for i = 1:4
        d = 3 * i - 2:3 * i;
        K(d, d) = K(d, d) + kIso;
    end
    for c = 5:8
        K = assemblePair(K, 9, c, diag([2.0e6, 2.0e6, 1.5e5]));
    end

    isoH = 0.03;
    model.nodeIds = (1:n)';
    model.coords = coords;
    model.M = M;
    model.K = K;
    model.baseIds = (101:104)';
    model.baseXyz = corners - [0 0 isoH];
    model.lines = [edges; 5 9; 6 9; 7 9; 8 9; (101:104)', (1:4)'; 101 102; 102 103; 103 104; 104 101];
    model.zetaRigid = 0.04;
    model.zetaElastic = 0.02;
    model.rigidCutoffHz = 200;
end

function K = assemblePair(K, i, j, ke)
    a = 3 * i - 2:3 * i;
    b = 3 * j - 2:3 * j;
    K(a, a) = K(a, a) + ke;
    K(b, b) = K(b, b) + ke;
    K(a, b) = K(a, b) - ke;
    K(b, a) = K(b, a) - ke;
end
