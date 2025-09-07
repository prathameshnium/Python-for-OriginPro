"""
Creates a new graph from the active worksheet in an OriginPro project.

This script uses the originpro library to find the currently active worksheet,
creates a new graph window, and generates a 2D plot using the first column for
the X-axis and the second column for the Y-axis. The graph axes are then
automatically rescaled to fit the data.
"""

import originpro as op
wks = op.find_sheet()
print(wks)

gp = op.new_graph()
 
gl = gp[0]
  
gl.add_plot(wks, 1, 0)
   
gl.rescale()
