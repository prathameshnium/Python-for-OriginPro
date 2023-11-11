import originpro as op
import seaborn as sns

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


for wb_index in range(starting,ending,steps):
    wks = op.find_sheet('w',wb_index)
    print(wks)

    plot=gl.add_plot(wks, 'M2','Temperature')
    #gl.group()

    #plot.colormap='Fire'
    pal =  sns.color_palette("Paired")# creates a colour pallete

    plot.color=str(pal.as_hex()[wb_index])#convert the pallet to hex , and select the iterating variable

    plot.symbol_size=4
    #lgnd = gl.label('Legend')


    lgnd = gp[0].label('Legend')
    legend_text = generate_legend_text(len(range(starting,ending,steps)))
    


    lgnd.text=legend_text


    
    
    
lgnd.set_int('left',4900)
lgnd.set_int('top',100)    
plot.colormap='Candy'    
gl.rescale()
