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
