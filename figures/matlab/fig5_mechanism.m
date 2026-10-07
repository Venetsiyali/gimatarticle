% fig5_mechanism.m
% Figure 5: why scattered dropouts cost skill and contiguous outages do not.
%
% Panel (a): availability of the boosted member against the share of records
%            retained, with the curve implied by the lag window (p^N_LAGS).
% Panel (b): median skill against that availability.
%
% Numbers are medians over the nine catchments, C1, lead 1, and are written
% out here so the figure is reproducible without the result files.
%
% Base MATLAB only: no toolboxes, no local functions.
% Outputs: fig5_mechanism.pdf (vector) and fig5_mechanism.png (600 dpi)

clear; close all; clc

%% ---------------------------------------------------------------- data
lab    = {'base','gap-3','gap-12','late-3','miss-5%','miss-10%','miss-20%'};
ret    = [1.0000 0.9973 0.9893 1.0000 0.9547 0.9253 0.8649];   % records retained
avail  = [0.9484 0.9413 0.9476 0.8465 0.6881 0.5690 0.3400];   % member available
ss     = [0.097  0.093  0.099  0.073  0.050  0.034  0.020 ];   % median SS, lead 1

fam    = [1 2 2 3 4 4 4];            % 1 base, 2 outage, 3 late, 4 dropout
famNm  = {'no failure','contiguous outage','late arrival','scattered dropout'};
famMk  = {'o','s','^','d'};
col    = [0.20 0.20 0.20;            % base      grey
          0.11 0.49 0.72;            % outage    blue
          0.90 0.62 0.00;            % late      amber
          0.78 0.17 0.17];           % dropout   red

N_LAGS = 6;
n      = numel(lab);

% Spearman rho without the Statistics Toolbox (no ties in these data)
ra = zeros(1,n);  [~,ia] = sort(avail);  ra(ia) = 1:n;
rb = zeros(1,n);  [~,ib] = sort(ss);     rb(ib) = 1:n;
rho = sum((ra-mean(ra)).*(rb-mean(rb))) / ...
      sqrt(sum((ra-mean(ra)).^2) * sum((rb-mean(rb)).^2));

%% ---------------------------------------------------------------- figure
fig = figure('Units','centimeters','Position',[2 2 17.0 7.6], ...
             'Color','w');
fs = 8;
set(fig,'DefaultAxesFontSize',fs,'DefaultTextFontSize',fs, ...
        'DefaultAxesFontName','Helvetica','DefaultTextFontName','Helvetica')

%% ---- panel (a) ------------------------------------------------------
ax1 = axes('Units','centimeters','Position',[1.6 1.45 6.4 5.4]); hold(ax1,'on')

p = linspace(0.80,1.0,400);
plot(ax1,p,p,':','Color',[0.72 0.72 0.72],'LineWidth',0.8)
plot(ax1,p,p.^N_LAGS,'-','Color',[0.45 0.45 0.45],'LineWidth',1.1)

for k = 1:n
    plot(ax1,ret(k),avail(k),famMk{fam(k)},'MarkerSize',6, ...
        'MarkerFaceColor',col(fam(k),:),'MarkerEdgeColor','none')
end

% base, gap-3 and gap-12 sit on top of one another: that coincidence is the
% point of the panel, so they carry one label with a leader line.
plot(ax1,[0.9792 0.9880],[1.0030 0.9570],'-','Color',[0.45 0.45 0.45], ...
     'LineWidth',0.5)
text(ax1,0.9772,1.0045,'base, gap-3, gap-12','FontSize',fs-1, ...
     'HorizontalAlignment','right','Color',[0.30 0.30 0.30])

idx = [4 5 6 7];                                  % late-3 and the dropouts
dx  = [ 0.005 -0.004 -0.004 -0.004];
dy  = [-0.048 -0.045 -0.045 -0.045];
ha  = {'left','right','right','right'};
for m = 1:numel(idx)
    k = idx(m);
    text(ax1,ret(k)+dx(m),avail(k)+dy(m),lab{k},'FontSize',fs-1, ...
        'HorizontalAlignment',ha{m},'Color',col(fam(k),:))
end

text(ax1,0.908,0.48,'p^{6}','FontSize',fs,'FontAngle','italic', ...
     'Color',[0.45 0.45 0.45])
text(ax1,0.878,0.905,'1:1','FontSize',fs-1,'Color',[0.72 0.72 0.72])

xlim(ax1,[0.845 1.012]); ylim(ax1,[0.25 1.04])
xlabel(ax1,'records retained'); ylabel(ax1,'boosted member available')
set(ax1,'XTick',0.85:0.05:1.00,'YTick',0.2:0.2:1.0, ...
        'Box','on','TickDir','out','LineWidth',0.6,'Layer','top')
title(ax1,'(a) the lag window, not the data loss', ...
      'FontWeight','normal','FontSize',fs)

%% ---- panel (b) ------------------------------------------------------
ax2 = axes('Units','centimeters','Position',[10.1 1.45 6.4 5.4]); hold(ax2,'on')

b  = polyfit(avail,ss,1);
xx = linspace(0.30,1.00,100);
plot(ax2,xx,polyval(b,xx),'-','Color',[0.45 0.45 0.45],'LineWidth',1.0)

for k = 1:n
    plot(ax2,avail(k),ss(k),famMk{fam(k)},'MarkerSize',6, ...
        'MarkerFaceColor',col(fam(k),:),'MarkerEdgeColor','none')
end

% same cluster, same treatment
plot(ax2,[0.845 0.930],[0.1095 0.0985],'-','Color',[0.45 0.45 0.45], ...
     'LineWidth',0.5)
text(ax2,0.838,0.1100,'base, gap-3, gap-12','FontSize',fs-1, ...
     'HorizontalAlignment','right','Color',[0.30 0.30 0.30])

idx2 = [4 5 6 7];
dx2  = [ 0.000  0.020  0.020  0.020];
dy2  = [-0.008  0.000  0.000  0.000];
ha2  = {'center','left','left','left'};
for m = 1:numel(idx2)
    k = idx2(m);
    text(ax2,avail(k)+dx2(m),ss(k)+dy2(m),lab{k},'FontSize',fs-1, ...
        'HorizontalAlignment',ha2{m},'Color',col(fam(k),:))
end

text(ax2,0.300,0.0905,sprintf('\\rho = %.2f',rho),'FontSize',fs-1, ...
     'Color',[0.35 0.35 0.35])

xlim(ax2,[0.28 1.06]); ylim(ax2,[0.005 0.115])
xlabel(ax2,'boosted member available')
ylabel(ax2,'median SS_{clim}, lead 1')
set(ax2,'XTick',0.3:0.2:0.9,'YTick',0.02:0.02:0.10, ...
        'Box','on','TickDir','out','LineWidth',0.6,'Layer','top')
title(ax2,'(b) and skill follows availability', ...
      'FontWeight','normal','FontSize',fs)

%% ---- legend ---------------------------------------------------------
hL = gobjects(1,4);
for f = 1:4
    hL(f) = plot(ax2,NaN,NaN,famMk{f},'MarkerSize',6, ...
        'MarkerFaceColor',col(f,:),'MarkerEdgeColor','none');
end
lg = legend(hL,famNm,'Location','southeast','Box','off','FontSize',fs-1);
lg.ItemTokenSize = [8 8];

%% ---------------------------------------------------------------- export
set(fig,'Units','centimeters');
pos = get(fig,'Position');
set(fig,'PaperUnits','centimeters','PaperSize',[pos(3) pos(4)], ...
        'PaperPosition',[0 0 pos(3) pos(4)]);

exportgraphics(fig,'fig5_mechanism.pdf','ContentType','vector', ...
               'BackgroundColor','white')
exportgraphics(fig,'fig5_mechanism.png','Resolution',600, ...
               'BackgroundColor','white')

fprintf('rho = %.3f\n',rho);
fprintf('written: fig5_mechanism.pdf and fig5_mechanism.png\n');
