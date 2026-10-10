% fig7_stationarity.m
% Figure 7: whether it pays to update depends on how long the record is.
%
% Skill of the two cheapest policies at each of the six catchments with
% complete records in both windows. Each line joins one catchment. In the
% short window the two policies are hard to separate; over four decades the
% catchments move the same way.
%
% Base MATLAB only: no toolboxes, no local functions.
% Outputs: fig7_stationarity.pdf (vector) and fig7_stationarity.png (600 dpi)

clear; close all; clc

%% ---------------------------------------------------------------- data
bas  = {'16176','16202','16279','16290','16300','17211'};

% SS_clim at lead 1, A2 feature construction, S-base
C0s  = [0.013 0.135 0.152 0.258 0.114 0.110];   % 1959-10 .. 1990-12
C1s  = [0.026 0.181 0.141 0.230 0.077 0.148];
C0l  = [0.056 0.050 0.080 0.077 0.075 0.068];   % 1970-01 .. 2010-12
C1l  = [0.072 0.060 0.123 0.113 0.093 0.057];

win  = {'1959-1990  (1125 dekads)','1970-2010  (1476 dekads)'};
A    = {C0s, C0l};
B    = {C1s, C1l};

up   = [0.11 0.49 0.72];     % updating helps
dn   = [0.78 0.17 0.17];     % updating hurts

%% ---------------------------------------------------------------- figure
fig = figure('Units','centimeters','Position',[2 2 13.0 7.6],'Color','w');
fs = 8;
set(fig,'DefaultAxesFontSize',fs,'DefaultTextFontSize',fs, ...
        'DefaultAxesFontName','Helvetica','DefaultTextFontName','Helvetica')

yl   = [-0.01 0.285];
xpos = [1 2];
left = [1.65 7.45];

for w = 1:2
    ax = axes('Units','centimeters','Position',[left(w) 1.55 4.9 5.2]);
    hold(ax,'on')

    plot(ax,[0.5 2.5],[0 0],'-','Color',[0.80 0.80 0.80],'LineWidth',0.6)

    a = A{w}; b = B{w};
    nUp = sum(b > a);

    for k = 1:numel(bas)
        c = up; if b(k) < a(k), c = dn; end
        plot(ax,xpos,[a(k) b(k)],'-','Color',c,'LineWidth',1.0)
        plot(ax,xpos,[a(k) b(k)],'o','MarkerSize',4.5, ...
            'MarkerFaceColor',c,'MarkerEdgeColor','w','LineWidth',0.4)
        % catchment code beside the C1 end, nudged apart where needed
        off = 0.0;
        if w == 2 && k == 2, off = -0.004; end
        if w == 2 && k == 6, off =  0.004; end
        text(ax,2.07,b(k)+off,bas{k},'FontSize',fs-2, ...
             'HorizontalAlignment','left','Color',c)
    end

    % medians, as a reference bar
    plot(ax,[0.80 1.20],[median(a) median(a)],'-', ...
         'Color',[0.35 0.35 0.35],'LineWidth',1.4)
    plot(ax,[1.80 2.20],[median(b) median(b)],'-', ...
         'Color',[0.35 0.35 0.35],'LineWidth',1.4)

    text(ax,1.5,0.272,sprintf('C1 better at %d of 6',nUp), ...
         'FontSize',fs-1,'HorizontalAlignment','center', ...
         'Color',[0.30 0.30 0.30])

    xlim(ax,[0.6 2.55]); ylim(ax,yl)
    set(ax,'XTick',xpos,'XTickLabel',{'C0  fit once','C1  refit yearly'}, ...
           'YTick',0:0.05:0.25,'Box','on','TickDir','out', ...
           'LineWidth',0.6,'Layer','top')
    title(ax,win{w},'FontWeight','normal','FontSize',fs)
    if w == 1
        ylabel(ax,'SS_{clim}, lead 1')
    else
        set(ax,'YTickLabel',[])
    end
end

%% ---------------------------------------------------------------- export
set(fig,'Units','centimeters');
pos = get(fig,'Position');
set(fig,'PaperUnits','centimeters','PaperSize',[pos(3) pos(4)], ...
        'PaperPosition',[0 0 pos(3) pos(4)]);

exportgraphics(fig,'fig7_stationarity.pdf','ContentType','vector', ...
               'BackgroundColor','white')
exportgraphics(fig,'fig7_stationarity.png','Resolution',600, ...
               'BackgroundColor','white')

fprintf('short window: median C0 %+.3f, C1 %+.3f, C1 better at %d of 6\n', ...
        median(C0s),median(C1s),sum(C1s>C0s));
fprintf('long  window: median C0 %+.3f, C1 %+.3f, C1 better at %d of 6\n', ...
        median(C0l),median(C1l),sum(C1l>C0l));
fprintf('written: fig7_stationarity.pdf and fig7_stationarity.png\n');
