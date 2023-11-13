import originpro as op
import pandas as pd
import numpy as np
starting=int(input("Enter the starting index for the plot , origin indexig start with 0 : "))
ending=int(input("Enter the Final index for the plot")) 
steps=int(input("Enter the step fot index for the plot")) 
df_wks= pd.DataFrame()
list1=list()
list2=list()

for wb_index in range(starting,ending+1,steps):
    wks = op.find_sheet('w',wb_index)
    list1.append(wb_index)
    list2.append(str(wks))


    
        
df_wks['Wb_Index'] =list1
df_wks['Wb_name'] =list2


# Create a new worksheet
wks = op.new_sheet()

# Load the DataFrame into the worksheet
wks.from_df(df_wks)
