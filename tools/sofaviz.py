import csv
import matplotlib.pyplot as plt
import numpy as np
import hashlib
import sys
# get the trace path from the first command line argument
trace_names=[];
trace_fids=[];
trace_timestamps=[];
colors=[];
radiis=[];

with open('calltrace.csv') as csvfile:
    reader = csv.DictReader(csvfile)
    offset = 30000
    
    for row in reader:
        skip = 0
        color = "grey"
        radii = 9
        timestamp = float(row['timestamp']) 
        func_name = row['func_name']
        fid = int(row['func_id'])
        if func_name.find("jpeg") >= 0:
            color="purple"
            radii=25
            fid = fid + offset  
        elif func_name.find("tensorflow") >= 0:
            color="orange"
            radii=9
            fid = fid + offset  
        elif func_name.find("cuda") >= 0:
            color="green"
            radii=25
            fid = fid + offset 
        elif func_name.find("CUDA") >= 0:
            color="green"
            radii=25
            fid = fid + offset 
        elif func_name.find("recv") >= 0:
            color="blue"
            radii=25
            fid = fid + offset 
        elif func_name.find("send") >= 0:
            color="blue"
            radii=25
            fid = fid + offset 
        elif func_name.find("xmit") >= 0:
            color="blue"
            radii=25
            fid = fid + offset 
        else:
            skip = 0
        
        if skip != 1:
            trace_timestamps.append(timestamp)
            trace_fids.append(fid)
            trace_names.append(func_name)
            colors.append(color)
            radiis.append(radii)
            #print("%lf %d %s" % ( timestamp, fid, func_name) )

x=[];y=[];count=0;
#for name in trace_names:
#    y.append(int(hashlib.sha224(bytes(name, 'utf-8')).hexdigest(),16))
for fid in trace_fids:
    y.append(fid)


for time in trace_timestamps:
    x.append(time)
#    if count > 1000:
#            break
#

#colors = np.random.rand(count)
#plt.scatter(x, y, c=colors, alpha=0.5)
plt.scatter(x, y, c=colors, s=radiis, alpha=0.5)
plt.show()

#plt.xlabel('Kernel Event ID')
#plt.ylabel('# of Calls of A Kernel Event')
#plt.show()
