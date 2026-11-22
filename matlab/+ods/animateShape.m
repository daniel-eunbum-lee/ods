function animateShape(res, freq, mode, cycles)
%ANIMATESHAPE Animate the deflection shape at one frequency in a MATLAB figure.
%   ods.animateShape(res, freq)                 % nearest bin to freq (Hz), 'el' view
%   ods.animateShape(res, freq, mode, cycles)   % mode 'abs' | 'rel' | 'el'; cycles=Inf loops
%   Close the figure to stop. Displacement is auto-scaled to ~12% of the model size; the
%   title gives the true peak amplitude per unit of table input.
    if nargin < 3 || isempty(mode), mode = 'el'; end
    if nargin < 4 || isempty(cycles), cycles = Inf; end
    t = res.test;
    [~, k] = min(abs(res.sp.f - freq));
    [U, nodeIds, measured] = ods.nodeShapes(res, k, mode);
    X0 = t.nodeXyz;

    mag = sqrt(sum(abs(U) .^ 2, 2));
    [umax, iMax] = max(mag);
    extent = norm(max(X0, [], 1) - min(X0, [], 1));
    amp = 0;
    if umax > 0, amp = 0.12 * extent / umax; end

    [~, la] = ismember(t.lines(:, 1), nodeIds);
    [~, lb] = ismember(t.lines(:, 2), nodeIds);
    ok = la > 0 & lb > 0;
    la = la(ok); lb = lb(ok);

    fig = figure('Name', sprintf('ODS %.2f Hz (%s)', res.sp.f(k), mode), 'Color', 'w');
    ax = axes('Parent', fig);
    hold(ax, 'on'); axis(ax, 'equal'); grid(ax, 'on'); view(ax, -35, 22);
    xlabel(ax, 'X'); ylabel(ax, 'Y'); zlabel(ax, 'Z');
    % undeformed ghost
    plot3(ax, [X0(la, 1) X0(lb, 1)]', [X0(la, 2) X0(lb, 2)]', [X0(la, 3) X0(lb, 3)]', ':', 'Color', [0.7 0.7 0.7]);
    hl = plot3(ax, [X0(la, 1) X0(lb, 1)]', [X0(la, 2) X0(lb, 2)]', [X0(la, 3) X0(lb, 3)]', '-', ...
        'Color', [0.16 0.47 0.84], 'LineWidth', 2);
    hn = scatter3(ax, X0(:, 1), X0(:, 2), X0(:, 3), 36, mag / max(umax, eps), 'filled');
    try
        colormap(ax, parula);   % not in GNU Octave
    catch
        colormap(ax, jet);
    end
    caxis(ax, [0 1]);
    if any(~measured)
        plot3(ax, X0(~measured, 1), X0(~measured, 2), X0(~measured, 3), 'kx');
    end
    pad = 0.15 * extent;
    lim = [min(X0, [], 1) - pad; max(X0, [], 1) + pad];
    axis(ax, lim(:)');
    title(ax, sprintf('%.2f Hz, %s view: max |u| = %.3g mm/%s at node %d (MPC %.3f)', res.sp.f(k), ...
        mode, umax, t.units, nodeIds(iMax), ods.mpc(U(measured, :))));

    phi = 0;
    dphi = 2 * pi / 40;
    while ishandle(fig) && phi < 2 * pi * cycles
        X = X0 + amp * real(U * exp(1i * phi));
        try
            for m = 1:numel(hl)
                set(hl(m), 'XData', X([la(m) lb(m)], 1), 'YData', X([la(m) lb(m)], 2), 'ZData', X([la(m) lb(m)], 3));
            end
            set(hn, 'XData', X(:, 1), 'YData', X(:, 2), 'ZData', X(:, 3));
            drawnow;
        catch
            break   % figure closed between the check and the update
        end
        pause(0.03);
        phi = phi + dphi;
    end
end
