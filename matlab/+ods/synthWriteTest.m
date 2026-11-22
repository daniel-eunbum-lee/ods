function synthWriteTest(outDir, model, sim)
%SYNTHWRITETEST Write a simulated run in the standard test-folder layout.
%   Writes time.mat, test.json, geometry.csv, channels.csv, lines.csv and truth.mat
%   (fn, zeta, phi, participation, node_ids). The Python tool reads the same files.
    if ~exist(outDir, 'dir'), mkdir(outDir); end
    data = sim.data;
    channels = {sim.channels.channel}';
    fs = sim.fs;
    save(fullfile(outDir, 'time.mat'), 'data', 'channels', 'fs', '-v7');

    fid = fopen(fullfile(outDir, 'test.json'), 'w');
    fprintf(fid, '{\n  "fs": %g,\n  "units": "g",\n  "excitation_axis": "%s",\n  "time_file": "time.mat"\n}\n', ...
        fs, sim.axis);
    fclose(fid);

    fid = fopen(fullfile(outDir, 'geometry.csv'), 'w');
    fprintf(fid, 'node,x,y,z,base\n');
    for i = 1:numel(model.nodeIds)
        fprintf(fid, '%d,%.4f,%.4f,%.4f,0\n', model.nodeIds(i), model.coords(i, :));
    end
    for i = 1:numel(model.baseIds)
        fprintf(fid, '%d,%.4f,%.4f,%.4f,1\n', model.baseIds(i), model.baseXyz(i, :));
    end
    fprintf(fid, '100,%.4f,%.4f,%.4f,1\n', mean(model.baseXyz, 1));
    fclose(fid);

    fid = fopen(fullfile(outDir, 'channels.csv'), 'w');
    fprintf(fid, 'channel,node,direction,role\n');
    for c = sim.channels
        fprintf(fid, '%s,%d,%s,%s\n', c.channel, c.node, c.direction, c.role);
    end
    fclose(fid);

    fid = fopen(fullfile(outDir, 'lines.csv'), 'w');
    fprintf(fid, 'node_a,node_b\n');
    fprintf(fid, '%d,%d\n', model.lines.');
    fclose(fid);

    truth = sim.modes;
    truth.node_ids = model.nodeIds;
    save(fullfile(outDir, 'truth.mat'), '-struct', 'truth', '-v7');
end
