function proj = nodeProjectors(nodeIds, channelNodes, channelDirs, channels)
%NODEPROJECTORS Per node: channel indices and a 3 x k pseudo-inverse (sensors -> xyz).
%   proj is a struct array with fields nodeId, idx (channel indices), P (3 x k).
%   Each sensor reads d . u, so k sensors at a node give D u = s with D (k x 3). The
%   pseudo-inverse gives least-squares u for >= 3 non-coplanar directions and the
%   minimum-norm u otherwise, i.e. unmeasured directions come out as zero motion.
    proj = struct('nodeId', {}, 'idx', {}, 'P', {});
    for i = 1:numel(nodeIds)
        idx = channels(channelNodes(channels) == nodeIds(i));
        if isempty(idx), continue; end
        D = channelDirs(idx, :);
        tol = 1e-6 * max(svd(D));
        proj(end + 1) = struct('nodeId', nodeIds(i), 'idx', idx(:)', 'P', pinv(D, tol)); %#ok<AGROW>
    end
end
