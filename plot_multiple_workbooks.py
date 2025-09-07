# Prg For Ploting Multiple Workbooks with option to specify Wks and Columns
#Updated On : 23 Nov 23

"""
Plots data from multiple OriginPro workbooks into a single graph.

This script offers two modes for selecting the source workbooks:
1.  **Range Mode (Input_Style = 0):** The user is prompted to enter a
    start, end, and step index to generate a range of workbooks to plot.
2.  **List Mode (Input_Style = 1):** The user can hardcode a specific list
    of workbook indices directly in the 'Wb_List' variable.

For each selected workbook, the script plots specified data columns onto a
single graph layer. The columns for the Y-axis and X-axis are defined by
their string names in the plotting loop (e.g., 'Measured Polarization' vs.
'Drive Voltage').

Finally, it generates a custom legend that references the plotted datasets
and their source worksheet names, then rescales the graph to fit all plots.
"""

import originpro as op
#import seaborn as sns
#import sys
#sys.path.append("C:\\Users\\Admin\\AppData\\Local\\Programs\\Python\\Python310\\Lib\\site-packages")




# Selecting Workbook : enter the list list of workbook or uncomment the range

Input_Style = 1 # 0 means Default range , 1 means User Difined List 

if Input_Style == 0:
    starting=int(input("Enter the starting index for the plot , origin indexig start with 0 : "))
    ending=int(input("Enter the Final index for the plot : ")) 
    steps=int(input("Enter the step fot index for the plot : ")) 
    Wb_List=range(starting,ending+1,steps) # For Multiple Workbook in a range
    print("Range selected with , Starting: "+str(starting)+" Ending :"+str(ending)+" Steps"+str(steps))
elif Input_Style == 1:
    Wb_List=[1,2,10] # For Multiple Workbook by specifing the list
    print("List Selected : "+str(Wb_List))
else:
    print('Error in Input Style for Worksheets to plot')


gp = op.new_graph() 
gl = gp[0]
def generate_legend_text(size):
    lgnd_template = '\\l({}) %({}, @ws)\n'
    result = ''

    for x in range(1, size + 1):
        lgnd_text = lgnd_template.format(x, x)
        result += lgnd_text

    return result




for wb_index in Wb_List:
    wks = op.find_sheet('w',wb_index)
    print(wks)
    
    """
    Commonly used Column names 
    "Frequency	Cp	G(1/Rp)	E1	E2	Z1	Z2	M1	M2	tand	sigma" "Field/Freq" "Temperature"
    "[500.0,1000.0,5000.0,10000.0,50000.0,100000.0,500000.0,1000000.0]"
    Drive Voltage
    Measured Polarization

    """

    
    for Col_Index in ['Measured Polarization']: # Specify Y , column names in above selectd workbooks 
        plot=gl.add_plot(wks,str(Col_Index),'Drive Voltage') #  Use this to specify , X here First Y then X axis
        #gl.group()
        
        
        plot.symbol_size=2
        
        
       # plot.colormap='Fire'
        #pal =  sns.color_palette("Paired")# creates a colour pallete
        #plot.color=str(pal.as_hex()[wb_index])#convert the pallet to hex , and select the iterating variable
        lgnd = gl.label('Legend')
        #lgnd = gp[0].label('Legend')
        legend_text = generate_legend_text(len(Wb_List))
        lgnd.text=legend_text


    
    
    
lgnd.set_int('left',4900)
lgnd.set_int('top',100)    
#plot.colormap='Candy'    
gl.rescale()
