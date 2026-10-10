% fig6_ablation.m
% Figure 6: the lag window is a design choice, not a property of the data.
%
% Median skill over the nine catchments against the rate of scattered
% dropout, for four ways of building the lag features. A0 is the
% construction inherited from the static study; A2 passes incomplete rows
% to the boosted member and lets it handle the gaps itself.
%
% Base MATLAB only: no toolboxes, no local functions.
% Outputs: fig6_ablation.pdf (vector) and fig6_ablation.png (600 dpi)

clear; close all; clc

%% ---------------------------------------------------------------- data
rate   = [0 5 10 20];                          % scattered dropout, per cent

% median SS_clim over nine catchments, C1, lead 1
ss     = [0.097 0.050 0.034 0.020;             % A0  six lags, row dropped
          0.118 0.072 0.066 0.056;             % A1  three lags, row dropped
          0.141 0.113 0.106 0.125;             % A2  six lags, gaps passed
          0.137 0.120 0.113 0.109];            % A3  A2 plus indicators

varNm  = {'A0  six lags, row dropped', ...
          'A1  three lags, row dropped', ...
          'A2  six lags, gaps passed', ...
          'A3  A2 plus indicators'};
varMk  = {'o','s','d','^'};
varCl  = [0.78 0.17 0.17;                      % A0  red
          0.90 0.62 0.00;                      % A1  amber
          0.11 0.49 0.72;                      % A2  blue
          0.45 0.45 0.45];                     % A3  grey

%% ---------------------------------------------------------------- figure
fig = figure('Units','centimeters','Position',[2 2 12.0 8.0],'Color','w');
fs = 8;
set(fig,'DefaultAxesFontSize',fs,'DefaultTextFontSize',fs, ...
        'DefaultAxesFontName','Helvetica','DefaultTextFontName','Helvetica')

ax = axes('Units','centimeters','Position',[1.7 1.5 9.9 5.6]); hold(ax,'on')

yl = [0.0 0.165];

% the benchmark itself
plot(ax,[-1 22],[0 0],'-','Color',[0.80 0.80 0.80],'LineWidth',0.6)

for v = [1 2 4 3]                               % A2 drawn last, on top
    plot(ax,rate,ss(v,:),'-','Color',varCl(v,:),'LineWidth',1.1)
end
for v = [1 2 4 3]
    plot(ax,rate,ss(v,:),varMk{v},'MarkerSize',6, ...
        'MarkerFaceColor',varCl(v,:),'MarkerEdgeColor','w','LineWidth',0.4)
end

% what each line loses between no failure and 20 per cent loss
for v = 1:4
    keep = ss(v,4)/ss(v,1);
    text(ax,20.6,ss(v,4),sprintf('%.0f%%',100*keep),'FontSize',fs-1, ...
        'HorizontalAlignment','left','Color',varCl(v,:))
end
text(ax,20.6,0.152,{'retained','at 20%'},'FontSize',fs-2, ...
     'HorizontalAlignment','left','Color',[0.45 0.45 0.45])

% the two ends of the story
text(ax,0.5,0.082,'A0 keeps a fifth of its skill','FontSize',fs-1, ...
     'HorizontalAlignment','left','Color',[0.78 0.17 0.17])
text(ax,0.5,0.1545,'A2 keeps almost all of it','FontSize',fs-1, ...
     'HorizontalAlignment','left','Color',[0.11 0.49 0.72])

xlim(ax,[-0.8 24.5]); ylim(ax,yl)
xlabel(ax,'scattered dropout (per cent of arriving records)')
ylabel(ax,'median SS_{clim}, lead 1')
set(ax,'XTick',rate,'YTick',0:0.04:0.16, ...
       'Box','on','TickDir','out','LineWidth',0.6,'Layer','top')

hL = gobjects(1,4);
for v = 1:4
    hL(v) = plot(ax,NaN,NaN,varMk{v},'MarkerSize',6, ...
        'MarkerFaceColor',varCl(v,:),'MarkerEdgeColor','w','LineWidth',0.4);
end
lg = legend(hL,varNm,'Location','southwest','Box','off','FontSize',fs-1);
lg.ItemTokenSize = [8 8];

%% ---------------------------------------------------------------- export
set(fig,'Units','centimeters');
pos = get(fig,'Position');
set(fig,'PaperUnits','centimeters','PaperSize',[pos(3) pos(4)], ...
        'PaperPosition',[0 0 pos(3) pos(4)]);

exportgraphics(fig,'fig6_ablation.pdf','ContentType','vector', ...
               'BackgroundColor','white')
exportgraphics(fig,'fig6_ablation.png','Resolution',600, ...
               'BackgroundColor','white')

for v = 1:4
    fprintf('%s: %.0f%% retained at 20%% loss\n', ...
            varNm{v}(1:2), 100*ss(v,4)/ss(v,1));
end
fprintf('written: fig6_ablation.pdf and fig6_ablation.png\n');
