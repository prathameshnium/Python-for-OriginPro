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
