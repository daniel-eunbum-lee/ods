function [U, nodeIds, measured] = nodeShapes(res, k, mode)
%NODESHAPES Complex xyz displacement (mm per unit input) of every node at bin k.
%   [U, nodeIds, measured] = ods.nodeShapes(res, k, mode)
%     mode     : 'abs' (as measured), 'rel' (relative to table), 'el' (rigid body removed)
%     U        : nn x 3 complex; animate real(U * exp(1i*phi))
%     measured : nn x 1 logical; unmeasured, non-base nodes are returned as zero
%   Base (table) nodes move with the table in 'abs' and are at rest otherwise.
    t = res.test;
    switch mode
        case 'abs', V = res.sp.T(k, :);
        case 'rel', V = res.Trel(k, :);
        case 'el',  V = res.Tel(k, :);
        otherwise, error('ods:nodeShapes', 'mode must be abs, rel or el');
    end
    sc = ods.accelToDisplacement(1, res.sp.f(k), t.units);
    proj = ods.nodeProjectors(t.nodeIds, t.channelNodes, t.channelDirs, t.responses);
    projIds = [proj.nodeId];

    nodeIds = t.nodeIds;
    nn = numel(nodeIds);
    U = zeros(nn, 3);
    measured = false(nn, 1);
    for i = 1:nn
        if t.nodeIsBase(i)
            measured(i) = true;
            if strcmp(mode, 'abs')
                U(i, :) = t.excitation * sc;
            end
            continue
        end
        j = find(projIds == nodeIds(i), 1);
        if isempty(j), continue; end
        U(i, :) = (proj(j).P * V(proj(j).idx).').' * sc;
        measured(i) = true;
    end
end
