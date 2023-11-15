import originpro as op
#import seaborn as sns

gp = op.new_graph() 
gl = gp[0]
def generate_legend_text(size):
    lgnd_template = '\\l({}) %({}, @ws)\n'
    result = ''

    for x in range(1, size + 1):
        lgnd_text = lgnd_template.format(x, x)
        result += lgnd_text

    return result
starting=int(input("Enter the starting index for the plot , origin indexig start with 0 : "))
ending=int(input("Enter the Final index for the plot")) 
steps=int(input("Enter the step fot index for the plot")) 


#Wb_List=range(starting,ending+1,steps)
Wb_List=[1]
#enter the list list of workbook or uncomment the range


for wb_index in Wb_List:
    wks = op.find_sheet('w',wb_index)
    print(wks)
    
    #Commonly used Col_names "Frequency	Cp	G(1/Rp)	E1	E2	Z1	Z2	M1	M2	tand	sigma" "Field/Freq"

    
    for Col_Index in [500.0,1000.0,5000.0,10000.0,50000.0,100000.0,500000.0,1000000.0]: # column names in above selectd workbooks
        plot=gl.add_plot(wks,str(Col_Index),'Field/Freq')
        #gl.group()
        plot.symbol_size=4
        #plot.colormap='Fire'
        #pal =  sns.color_palette("Paired")# creates a colour pallete
        #plot.color=str(pal.as_hex()[wb_index])#convert the pallet to hex , and select the iterating variable
        #lgnd = gl.label('Legend')
        lgnd = gp[0].label('Legend')
        legend_text = generate_legend_text(len(Wb_List))
        lgnd.text=legend_text


    
    
    
lgnd.set_int('left',4900)
lgnd.set_int('top',100)    
#plot.colormap='Candy'    
gl.rescale()
