import originpro as op
gp = op.new_graph() 
gl = gp[0]
def generate_legend_text(size):
    lgnd_template = '\\l({}) %({}, @ws)\n'
    result = ''

    for x in range(1, size + 1):
        lgnd_text = lgnd_template.format(x, x)
        result += lgnd_text

    return result
 


for wb_index in range(40):
    wks = op.find_sheet('w',wb_index)
    print(wks)

    plot=gl.add_plot(wks, 'tand','Temperature')
    #gl.group()

    plot.colormap='Fire'
    plot.symbol_size=4

    lgnd = gp[0].label('Legend')
    legend_text = generate_legend_text(40)

    lgnd.text=legend_text


    
    
    
lgnd.set_int('left',4900)
lgnd.set_int('top',100)    
plot.colormap='Candy'    
gl.rescale()
