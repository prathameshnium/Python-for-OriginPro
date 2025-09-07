"""
Imports a text-based data file and plots multiple specified columns
into a single scatter graph in OriginPro.

This script performs the following steps:
1.  Reads a tab-delimited text file into a pandas DataFrame.
2.  Imports the DataFrame into a new worksheet in the current Origin project.
3.  Creates a new graph using a 'scatter' template.
4.  Iterates through a specified range of column indices, plotting each one
    as a separate data series against the first column (index 0) on the X-axis.
5.  Groups all the plots on the graph layer to apply uniform styling.
6.  Customizes the grouped plots with a 'Candy' colormap, varied symbol
    shapes, and a larger symbol size.
7.  Adjusts the legend's font size, position, and removes its frame.
8.  Finally, rescales the axes to fit all plotted data.
"""

import pandas as pd
import originpro as op




 

df=pd.read_table('C:/Users/ketan/OneDrive/Desktop/LTNO-MN-newCp.txt',)

wks = op.new_sheet()
wks=op.find_sheet()
wks.from_df(df)

graph = op.new_graph(template='scatter')
gl=graph[0]

# plot whole sheet as XY plot
ind=78
plot = gl.add_plot(wks,colx=0,coly=ind)
for ind in range(10,202,25):
    plot = gl.add_plot(wks,colx=0,coly=ind)
#plot = gl.add_plot(f'{wks.lt_range()}!(?,1:end)')

# group the plots and control plots setting in group
gl.group()
plot.colormap = 'Candy'
plot.shapelist = [3, 2, 1]
plot.symbol_size=5


gl.rescale()

# Customize Legend
lgnd = gl.label('Legend')
lgnd.set_int('fsize',10 )
lgnd.set_int('left',105.51378)
lgnd.set_int('top',4.9533)
lgnd.set_int('showframe',0)


--------------------------------------------------------------------------------------------------------------------
