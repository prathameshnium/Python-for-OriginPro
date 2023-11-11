import originpro as op
gp = op.new_graph()
 
gl = gp[0]
  
   


for wb_index in range(40):
    wks = op.find_sheet('w',wb_index)
    print(wks)
    gl.add_plot(wks, 1, 0)

    
gl.rescale()
