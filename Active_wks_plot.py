import originpro as op
wks = op.find_sheet()
print(wks)

gp = op.new_graph()
 
gl = gp[0]
  
gl.add_plot(wks, 1, 0)
   
gl.rescale()
