"""
Scans the current OriginPro project to find all existing worksheets and
creates a new summary sheet containing their names and indices.

This script performs the following actions:
1.  Prompts the user with an input dialog to begin the scan.
2.  Iterates through all worksheets by index, starting from 0.
3.  For each worksheet found, it records its index number and name.
4.  The loop continues until no more worksheets are found at the next index.
5.  The collected indices and names are compiled into a pandas DataFrame.
6.  Finally, a new worksheet is created and populated with this DataFrame,
    effectively generating a "Table of Contents" for the project's data.
"""

import originpro as op
import pandas as pd
import numpy as np
#starting=int(input("Enter the starting index for the plot , origin indexig start with 0 : "))
#ending=int(input("Enter the Final index for the plot")) 
#steps=int(input("Enter the step fot index for the plot")) 
df_wks= pd.DataFrame()
list1=list()
list2=list()
steps=0


comments=input("Create List of Worksheets , Just Click on Ok: ")

print("Comment: "+str(comments))
while True:
    wb_index=steps
    wks = op.find_sheet('w',wb_index)
    if str(wks)!= "None":
        list1.append(wb_index)
        list2.append(str(wks))
        print("Index : "+str(wb_index)+"  |  "+str(wks))
        steps+=1
    else :
        break
    
    


#for wb_index in range(starting,ending+1,steps)    
df_wks['Wb_Index'] =list1
df_wks['Wb_name'] =list2

print("Workbook List is Saved")




# Create a new worksheet
wks = op.new_sheet()

# Load the DataFrame into the worksheet
wks.from_df(df_wks)
