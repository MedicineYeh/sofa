#!/usr/bin/python
from scapy.all import *
import sqlite3
import pandas as pd
import numpy as np
import csv
import cxxfilt
import json

print 'Number of arguments:', len(sys.argv), 'arguments.'
print 'Argument List:', str(sys.argv) 
logdir = []
filein = []

if len(sys.argv) < 2:
    print("Usage: sofa-preproc.py /path/to/logdir")
    quit();
else:
    logdir = sys.argv[1] + "/"
    filein = logdir+"gputrace.nvp"
    
class CPUTrace:
    fieldnames = ['time', "event", "duration", "deviceId", "pid", "tid", "data", "pkt_src", "pkt_dst"]
    time=0
    duration=0
    event=-1
    vaddr=-1
    deviceId=-1
    pid=-1
    tid=-1
    data=0
    pkt_src=-1
    pkt_dst=-1
    def info(self):
	    return 'hello world'

with open(logdir+'sofa_time.txt') as f:
    t_glb_base = float(f.readlines()[0])
    print t_glb_base

iptable=[]


cputrace = CPUTrace()
with open(logdir+'cputrace.csv', 'w') as csvfile: 
    writer = csv.DictWriter(csvfile, fieldnames=cputrace.fieldnames)
    writer.writeheader()
    packets = rdpcap(logdir+'sofa.pcap')
    t_base = 0
    for i in range(0,len(packets)):
        time = packets[i][IP].time
        if i == 0:
            t_base = time
        if ( i % 1 ) == 0 :
            t_begin = (time - t_base) + t_glb_base
            t_end = (time - t_base) + t_glb_base
            duration = t_end - t_begin
            cputrace.time = t_begin
            cputrace.pkt_src = packets[i][IP].src.split('.')[3]
    	    cputrace.pkt_dst = packets[i][IP].dst.split('.')[3]
    	    cputrace.data = packets[i].len
            writer.writerow({'time': cputrace.time, 'event':cputrace.event, 'pid':cputrace.pid, 'tid':cputrace.tid, 'deviceId':cputrace.deviceId, 'duration':cputrace.duration, 'data': cputrace.data, 'pkt_src':cputrace.pkt_src, 'pkt_dst':cputrace.pkt_dst })
            #print("%lf [%d] src:%s dst:%s len:%d " % ( cputrace.time, i, cputrace.pkt_src, cputrace.pkt_dst, cputrace.data))

cputrace = CPUTrace()
with open(logdir+'cputrace.csv', 'a') as csvfile: 
    writer = csv.DictWriter(csvfile, fieldnames=cputrace.fieldnames)
    #9424/9424  [006] 18170.649588:          1  ffffffff8106315a native_write_msr_safe
    with open(logdir+'perf.script') as f:
        lines = f.readlines()
        t_base = 0
        for i in range(0,len(lines)):
            fields = lines[i].split()
            time = float(fields[2].split(':')[0])
            if i == 0:
                t_base = time 
            func_name = fields[5]
            if ( i % 1 ) == 0 :
                t_begin = time - t_base  + t_glb_base
                t_end = time - t_base + t_glb_base
                duration = t_end - t_begin
                cputrace.time=t_begin
                cputrace.pid = fields[0].split('/')[0]
                cputrace.tid = fields[0].split('/')[1]
                cputrace.vaddr=int("0x"+fields[4],16)%1000000
                cputrace.event=cputrace.vaddr
                cputrace.deviceId=int(fields[1].split('[')[1].split(']')[0])
                cputrace.duration=int(fields[3])*(1.0/3e9)
                cputrace.data=0
                writer.writerow({'time': cputrace.time, 'event':cputrace.event, 'pid':cputrace.pid, 'tid':cputrace.tid, 'deviceId':cputrace.deviceId, 'duration':cputrace.duration, 'data': cputrace.data, 'pkt_src':cputrace.pkt_src, 'pkt_dst':cputrace.pkt_dst })
    csvfile.close()
print("Read nvprof traces ...")
sqlite_file = filein
db = sqlite3.connect(sqlite_file)
cursor = db.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
i=0;
ftable=[];
for table_name in tables: 
    i=i+1
    tname = table_name[0]
    table = pd.read_sql_query("SELECT * from %s" % tname, db)
    #print("table-%d = %s, count=%d" % (i,tname,len(table.index)) )
    if len(table.index) > 0:
        table.to_csv(logdir + tname + '.csv', index_label='index')
    if tname == "StringTable":
        ftable=table

class GPUTrace:
    fieldnames = ['time', "event", "duration","copyKind", "deviceId", "data_B", "streamId"]
    time=0
    event=0
    copyKind=0
    deviceId=0
    streamId=0
    duration=0
    size=0
    def info(self):
	    return 'hello world'

gputrace = GPUTrace()

cursor.execute("SELECT start,end,name,streamId,deviceId FROM CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL")
records = cursor.fetchall()
i=0
begin = []
end = []
event = []
t_base = 0
gputraces = []
with open(logdir+'gputrace.csv', 'w') as csvfile: 
    writer = csv.DictWriter(csvfile, fieldnames=gputrace.fieldnames)
    writer.writeheader()
    for record in records:
        i = i + 1
        if i == 1:
            t_base = record[0]
        if ( i % 1 ) == 0 :
            t_begin = (record[0] -t_base)/1e9 + t_glb_base
            t_end = (record[1]- t_base)/1e9 + t_glb_base
            duration = t_end - t_begin
            begin = np.append(begin, t_begin )
            end = np.append(end, t_end )
            func_name = cxxfilt.demangle( ("%s" % ftable.loc[ftable._id_==record[2],'value'])) 
            event_id = record[2]
            gputrace.time=t_begin
            gputrace.event=record[2]
            gputrace.copyKind=-1
            gputrace.deviceId=record[4]
            gputrace.streamId=record[3]
            gputrace.duration=duration
            gputrace.data=0
            #print("event id and its name = %d %s" % (event_id,func_name)) 
            event = np.append(event, event_id)
            #print("record-%d: %s at %lf, duration = %lf" % (i,record, t_begin, t_end-t_begin) )
            writer.writerow({'time': gputrace.time, 'event': gputrace.event, 'copyKind': gputrace.copyKind, 'deviceId':gputrace.deviceId, 'streamId':gputrace.streamId, 'duration':gputrace.duration, 'data_B': gputrace.data })
    csvfile.close()
#index,_id_,copyKind,srcKind,dstKind,flags,bytes,start,end,deviceId,contextId,streamId,correlationId,runtimeCorrelationId
cursor.execute("SELECT start,end,bytes,copyKind,deviceId,srcKind,dstKind,streamId  FROM CUPTI_ACTIVITY_KIND_MEMCPY")
records = cursor.fetchall()
i=0
begin = []
end = []
event = []
t_base = 0
with open(logdir+'gputrace.csv', 'a') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=gputrace.fieldnames)
    for record in records:
        i = i + 1
        if i == 1:
            t_base = record[0]
        if ( i % 10 ) == 0 :
            t_begin = (record[0] - t_base)/1e9 + t_glb_base
            t_end = (record[1]- t_base)/1e9 + t_glb_base
            duration = t_end - t_begin
            begin = np.append(begin, t_begin )
            end = np.append(end, t_end )
            gputrace.time=t_begin
            gputrace.event=-1 
            gputrace.copyKind=record[3]
            gputrace.deviceId=record[4]
            gputrace.streamId=record[7]
            gputrace.duration=duration
            gputrace.data=record[2]
            writer.writerow({'time': gputrace.time, 'event': gputrace.event, 'copyKind': gputrace.copyKind, 'deviceId':gputrace.deviceId, 'streamId':gputrace.streamId, 'duration':gputrace.duration, 'data_B': gputrace.data })

cursor.execute("SELECT start,end,bytes,copyKind,deviceId,srcKind,dstKind,streamId  FROM CUPTI_ACTIVITY_KIND_MEMCPY2")
records = cursor.fetchall()
begin = []
end = []
event = []
with open(logdir+'gputrace.csv', 'a') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=gputrace.fieldnames)
    t_base = 0
    i=0
    for record in records:
        i = i + 1
        if i == 1:
            t_base = record[0]
        if ( i % 10 ) == 0 :
            t_begin = (record[0] - t_base)/1e9 + t_glb_base
            t_end = (record[1]- t_base)/1e9 + t_glb_base
            duration = t_end - t_begin
            begin = np.append(begin, t_begin )
            end = np.append(end, t_end )
            gputrace.time=t_begin
            gputrace.event=-1
            gputrace.copyKind=record[3]
            gputrace.deviceId=record[4]
            gputrace.streamId=record[7]
            gputrace.duration=duration
            gputrace.data=record[2]
            writer.writerow({'time': gputrace.time, 'event': gputrace.event, 'copyKind': gputrace.copyKind, 'deviceId':gputrace.deviceId, 'streamId':gputrace.streamId, 'duration':gputrace.duration, 'data_B': gputrace.data })


#cursor.execute("SELECT start,end,bytes,copyKind,deviceId,srcKind,dstKind,streamId  FROM CUPTI_ACTIVITY_KIND_MEMCPY2")
#records = cursor.fetchall()
#i=0
#begin = []
#end = []
#event = []
#t_base = 0
#with open('gputrace_memcpy2.csv', 'w') as csvfile:
#    fieldnames = ['begin', "duration", "bytes", "copyKind", "deviceId", "srcKind","dstKind","streamId"]
#    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
#    writer.writeheader()
#    for record in records:
#        i = i + 1
#        if i == 1:
#            t_base = record[0]
#        if ( i % 1 ) == 0 :
#            print(record)
#            t_begin = record[0] - t_base
#            t_end = record[1]- t_base
#            duration = t_end - t_begin
#            writer.writerow({'begin': t_begin, 'duration': duration, 'bytes': record[2], 'copyKind':record[3], 'deviceId':record[4], 'srcKind':record[5], 'dstKind':record[6], 'streamId':record[7] })
# 



    
#for record in records:
#    i = i + 1
#    if i == 1:
#        t_base = record[0]/1000
#    if ( i % 10 ) == 0 :
#        print(record)
#        end = np.append(end, t_end )
#        func_name = ftable.loc[ftable._id_==record[2],'value']
#        event = np.append(event, func_name)
#        print("record-%d: %s at %d, duration = %d" % (i,record, t_begin, t_end-t_begin) )
#        print("ID-%d = %s" % ( record[2], func_name ))
#        print("t_base = %d" % t_base) 
#plt.barh(range(len(begin)),  end-begin, left=begin)
#plt.yticks(range(len(begin)), event)
#plt.show()
