% fig4_failuregrid.m
% Figure 4: which delivery failures cost skill, and which do not.
%
% Median SS_clim over the nine catchments for every failure scenario and
% lead time, under C1. Shading is the share of the undisturbed skill that
% the scenario retains at that lead; the number in each cell is the skill
% itself.
%
% Base MATLAB only: no toolboxes, no local functions.
% Outputs: fig4_failuregrid.pdf (vector) and fig4_failuregrid.png (600 dpi)

clear; close all; clc

%% ---------------------------------------------------------------- data
% rows ordered by family, ending with the one that matters
row = {'S-base', ...
       'S-gap-03','S-gap-06','S-gap-12', ...
       'S-late-1','S-late-2','S-late-3', ...
       'S-drift-10','S-drift-25', ...
       'S-spike-01','S-spike-03', ...
       'S-miss-05','S-miss-10','S-miss-20'};

fam = {'no failure','contiguous outage','late arrival', ...
       'gauge drift','isolated spike','scattered dropout'};
famRow = [1 1; 2 4; 5 7; 8 9; 10 11; 12 14];

ss = [0.097 0.130 0.154;      % base
      0.093 0.119 0.140;      % gap-3
      0.090 0.140 0.147;      % gap-6
      0.099 0.141 0.136;      % gap-12
      0.099 0.132 0.144;      % late-1
      0.091 0.126 0.146;      % late-2
      0.073 0.110 0.115;      % late-3
      0.068 0.095 0.117;      % drift-10
      0.062 0.083 0.098;      % drift-25
      0.075 0.093 0.114;      % spike-1
      0.069 0.112 0.123;      % spike-3
      0.050 0.080 0.076;      % miss-5
      0.034 0.048 0.043;      % miss-10
      0.020 0.027 0.025];     % miss-20

npos = [9 9 9 9 9 9 9 9 9 8 8 9 9 9];   % catchments with positive skill

rowLab = row;                       % the two spike rows carry a footnote
rowLab{10} = 'S-spike-01*';
rowLab{11} = 'S-spike-03*';

nR = size(ss,1);  nC = 3;
rat = ss ./ repmat(ss(1,:),nR,1);       % share of undisturbed skill

%% ---------------------------------------------------------------- colour
% pale to deep blue, built by hand so no toolbox is needed
lo = [0.97 0.97 0.99];  mid = [0.62 0.79 0.89];  hi = [0.06 0.33 0.56];
t  = linspace(0,1,128)';
cm = [lo + (mid-lo).*t; mid + (hi-mid).*t];

cLo = 0.12; cHi = 1.10;                 % colour limits on the ratio

%% ---------------------------------------------------------------- figure
fig = figure('Units','centimeters','Position',[2 2 12.2 11.5],'Color','w');
fs = 8;
set(fig,'DefaultAxesFontSize',fs,'DefaultTextFontSize',fs, ...
        'DefaultAxesFontName','Helvetica','DefaultTextFontName','Helvetica')

ax = axes('Units','centimeters','Position',[4.35 2.35 5.0 8.3]); hold(ax,'on')

imagesc(ax,rat,[cLo cHi]); colormap(ax,cm)
set(ax,'YDir','reverse')

for i = 1:nR
    for j = 1:nC
        if rat(i,j) > 0.78, tc = [1 1 1]; else, tc = [0.15 0.15 0.15]; end
        text(ax,j,i,sprintf('%.3f',ss(i,j)),'FontSize',fs-1, ...
             'HorizontalAlignment','center','Color',tc)
    end
end

% family separators
for k = 1:size(famRow,1)-1
    y = famRow(k,2)+0.5;
    plot(ax,[0.5 nC+0.5],[y y],'-','Color',[1 1 1],'LineWidth',1.6)
end

xlim(ax,[0.5 nC+0.5]); ylim(ax,[0.5 nR+0.5])
set(ax,'XTick',1:nC,'XTickLabel',{'lead 1','lead 2','lead 3'}, ...
       'YTick',1:nR,'YTickLabel',rowLab,'TickLength',[0 0], ...
       'Box','on','LineWidth',0.6,'Layer','top','XAxisLocation','top')

% family names down the left
for k = 1:size(famRow,1)
    ym = mean(famRow(k,:));
    text(ax,-0.75,ym,fam{k},'FontSize',fs-2,'Rotation',0, ...
         'HorizontalAlignment','right','Color',[0.45 0.45 0.45])
end

% footnote for the two rows where one catchment turns negative
text(ax,nC+0.5,nR+1.35,'* 8 of 9 catchments positive; 9 of 9 elsewhere', ...
     'FontSize',fs-2,'Color',[0.45 0.45 0.45], ...
     'HorizontalAlignment','right','Interpreter','none')

%% ---- colour bar ------------------------------------------------------
cb = axes('Units','centimeters','Position',[9.65 2.35 0.42 8.3]);
imagesc(cb,linspace(cHi,cLo,256)'); colormap(cb,flipud(cm))
set(cb,'XTick',[],'YDir','normal','Box','on','LineWidth',0.6, ...
       'YTick',linspace(1,256,5), ...
       'YTickLabel',{'0.2','0.4','0.6','0.8','1.0'}, ...
       'YAxisLocation','right','TickLength',[0 0],'FontSize',fs-1)
ylabel(cb,'share of undisturbed skill','FontSize',fs-1)

annotation('textbox',[0.02 0.015 0.96 0.05],'String', ...
  'Outages cost nothing; scattered dropout costs almost everything.', ...
  'EdgeColor','none','FontSize',fs-1,'Color',[0.30 0.30 0.30], ...
  'HorizontalAlignment','center')

%% ---------------------------------------------------------------- export
set(fig,'Units','centimeters');
pos = get(fig,'Position');
set(fig,'PaperUnits','centimeters','PaperSize',[pos(3) pos(4)], ...
        'PaperPosition',[0 0 pos(3) pos(4)]);

exportgraphics(fig,'fig4_failuregrid.pdf','ContentType','vector', ...
               'BackgroundColor','white')
exportgraphics(fig,'fig4_failuregrid.png','Resolution',600, ...
               'BackgroundColor','white')

fprintf('lead 1, share retained: gap-12 %.2f, late-3 %.2f, miss-20 %.2f\n', ...
        rat(4,1),rat(7,1),rat(14,1));
fprintf('written: fig4_failuregrid.pdf and fig4_failuregrid.png\n');
