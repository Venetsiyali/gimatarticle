% fig3_pareto.m
% Figure 3: skill against the cost of keeping the model current.
%
% Median skill score over the nine catchments for the five update policies,
% plotted against the total fitting time each policy spends per catchment.
% Numbers are written out here so the figure is reproducible without the
% result files.
%
% Base MATLAB only: no toolboxes, no local functions.
% Outputs: fig3_pareto.pdf (vector) and fig3_pareto.png (600 dpi)

clear; close all; clc

%% ---------------------------------------------------------------- data
pol    = {'C0','C3','C1','C2','C4'};          % ordered by cost
nfit   = [    1   753    21   126   753];     % number of refits
cost   = [0.161 0.199 3.841 23.527 138.193];  % total fitting time, s
descr  = {'once','incremental','yearly','6-dekad','every step'};

% median SS_clim over nine catchments, leads 1-3
ss     = [0.100 0.077 0.097 0.106 0.105;      % lead 1
          0.125 0.085 0.130 0.128 0.119;      % lead 2
          0.108 0.102 0.154 0.156 0.160];     % lead 3

% catchments significant after Holm, out of nine
holm   = [    4     2     8     7     7;
              8     4     7     7     8;
              6     4     6     9     9];

leadNm = {'lead 1','lead 2','lead 3'};
leadMk = {'o','s','^'};
leadCl = [0.05 0.30 0.52;
          0.25 0.57 0.75;
          0.60 0.78 0.88];

%% ---------------------------------------------------------------- figure
fig = figure('Units','centimeters','Position',[2 2 12.0 8.0],'Color','w');
fs = 8;
set(fig,'DefaultAxesFontSize',fs,'DefaultTextFontSize',fs, ...
        'DefaultAxesFontName','Helvetica','DefaultTextFontName','Helvetica')

ax = axes('Units','centimeters','Position',[1.7 1.5 9.9 5.3]); hold(ax,'on')
set(ax,'XScale','log')

% guide lines at each policy, labelled on top
yl = [0.065 0.172];
% C0 and C3 are only 20 % apart in cost, so their labels are set back to back
hal = {'right','left','center','center','center'};
off = [0.94 1.06 1.0 1.0 1.0];
for k = 1:numel(pol)
    plot(ax,[cost(k) cost(k)],yl,':','Color',[0.82 0.82 0.82],'LineWidth',0.5)
    text(ax,cost(k)*off(k),yl(2)-0.004,pol{k},'FontSize',fs, ...
         'FontWeight','bold','HorizontalAlignment',hal{k}, ...
         'Color',[0.25 0.25 0.25])
    text(ax,cost(k)*off(k),yl(2)-0.0105,descr{k},'FontSize',fs-2, ...
         'HorizontalAlignment',hal{k},'Color',[0.55 0.55 0.55])
end

% the three lead series, drawn in cost order
for L = 1:3
    plot(ax,cost,ss(L,:),'-','Color',leadCl(L,:),'LineWidth',1.0)
end
for L = 1:3
    plot(ax,cost,ss(L,:),leadMk{L},'MarkerSize',6, ...
        'MarkerFaceColor',leadCl(L,:),'MarkerEdgeColor','w','LineWidth',0.4)
end

% the elbow
plot(ax,[3.841 3.841],[0.0695 0.0885],'-','Color',[0.78 0.17 0.17], ...
     'LineWidth',0.8)
text(ax,3.0,0.0675,'elbow','FontSize',fs-1,'Color',[0.78 0.17 0.17], ...
     'HorizontalAlignment','center')

% C3 is cheap and poor: say why, once
text(ax,0.27,0.0735,{'trees are not','refitted in place'},'FontSize',fs-2, ...
     'HorizontalAlignment','left','Color',[0.45 0.45 0.45])

% C1 to C4 costs 36x for little
plot(ax,[4.6 115],[0.1135 0.1135],'-','Color',[0.45 0.45 0.45],'LineWidth',0.5)
plot(ax,[4.6 4.6],[0.1135 0.1165],'-','Color',[0.45 0.45 0.45],'LineWidth',0.5)
plot(ax,[115 115],[0.1135 0.1165],'-','Color',[0.45 0.45 0.45],'LineWidth',0.5)
text(ax,23,0.1185,'36x the cost, +0.006 at lead 3','FontSize',fs-2, ...
     'HorizontalAlignment','center','Color',[0.45 0.45 0.45])

xlim(ax,[0.09 320]); ylim(ax,yl)
xlabel(ax,'fitting time per catchment (s, log scale)')
ylabel(ax,'median SS_{clim} over nine catchments')
set(ax,'XTick',[0.1 1 10 100],'XTickLabel',{'0.1','1','10','100'}, ...
       'YTick',0.08:0.02:0.16,'Box','on','TickDir','out', ...
       'LineWidth',0.6,'Layer','top')

hL = gobjects(1,3);
for L = 1:3
    hL(L) = plot(ax,NaN,NaN,leadMk{L},'MarkerSize',6, ...
        'MarkerFaceColor',leadCl(L,:),'MarkerEdgeColor','w','LineWidth',0.4);
end
lg = legend(hL,leadNm,'Location','southeast','Box','off','FontSize',fs-1);
lg.ItemTokenSize = [8 8];

%% ---------------------------------------------------------------- export
set(fig,'Units','centimeters');
pos = get(fig,'Position');
set(fig,'PaperUnits','centimeters','PaperSize',[pos(3) pos(4)], ...
        'PaperPosition',[0 0 pos(3) pos(4)]);

exportgraphics(fig,'fig3_pareto.pdf','ContentType','vector', ...
               'BackgroundColor','white')
exportgraphics(fig,'fig3_pareto.png','Resolution',600, ...
               'BackgroundColor','white')

fprintf('C1 to C4: %.0fx cost, lead-3 gain %+.3f\n', ...
        cost(5)/cost(3), ss(3,5)-ss(3,3));
fprintf('written: fig3_pareto.pdf and fig3_pareto.png\n');
