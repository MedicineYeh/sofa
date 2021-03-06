#!/usr/bin/python
import os
import sys
import pandas as pd
import numpy as np
import csv
import json
import random
from operator import itemgetter, attrgetter
import argparse
import multiprocessing as mp
from functools import partial
from sofa_print import *
from sofa_config import *


class Event:

    def __init__(self, name, ttype, timestamp, duration):
        self.name = name
        self.ttype = ttype  # 0 for begin, 1 for end
        self.timestamp = timestamp
        self.duration = duration

    def __repr__(self):
        return repr((self.name, self.ttype, self.timestamp, self.duration))

# Assume pa<pb, pc<pd:


def overlap(pa, pb, pc, pd):
    if pb - pc >= 0 and pd - pa >= 0:
        return min(pb, pd) - max(pa, pc)


# print_format_table()
cktable = {-1: "KER", 1: "H2D", 2: "D2H", 8: "D2D", 10: "P2P"}
ckindex = [1, 2, 8, 10]

def comm_profile(cfg, df_gpu):
    total_traffic = 0.0
    total_h2d_traffic = 0.0
    total_d2h_traffic = 0.0
    total_p2p_traffic = 0.0
    total_memcopy_time = 0.0

    n_gpus = 0
    for i in range(len(df_gpu)):
        if df_gpu.loc[i,'deviceId']+1 > n_gpus:
            n_gpus = df_gpu.loc[i,'deviceId']+1
    
    print_title("Data Traffic for each CopyKind (MB)")
    data_copyKind = grouped_df = df_gpu.groupby("copyKind")["payload"]
    for key, item in grouped_df:
        print(
            "[%s]: %lf" %
            (cktable[key], grouped_df.get_group(key).sum() / 1000000.0))
        if int(key) == 1:
            total_h2d_traffic = grouped_df.get_group(key).sum() / 1000000.0
        if int(key) == 2:
            total_d2h_traffic = grouped_df.get_group(key).sum() / 1000000.0
        if int(key) == 10:
            total_p2p_traffic = grouped_df.get_group(key).sum() / 1000000.0
        if int(key) != 8:
            total_traffic = total_traffic + \
                grouped_df.get_group(key).sum() / 1000000.0
    print("Total traffic: %.2lf" % total_traffic)

       
    print_title("Data Communication Time for each CopyKind (s)")
    durations_copyKind = grouped_df = df_gpu.groupby("copyKind")["duration"]
    for key, item in grouped_df:
        print("[%s]: %lf" % (cktable[key], grouped_df.get_group(key).sum()))
        if key == -1:
            total_kernel_time = grouped_df.get_group(key).sum()
        else:
            total_memcopy_time = total_memcopy_time + \
                grouped_df.get_group(key).sum()

    
    bw = (data_copyKind.sum() / 1000000) / durations_copyKind.sum() / 1000
    bw_h2d = bw_d2h = bw_p2p = avg_bw = 1e-10
    

    total_weights = 0
    for i in range(len(bw)):
        key = bw.keys()[i]
        if cktable[key] == 'D2D':
            continue
        if cktable[key] == 'H2D':
            total_weights = total_h2d_traffic + total_weights
            avg_bw = avg_bw + bw.iloc[i] * float(total_h2d_traffic)/total_weights
            bw_h2d = bw.iloc[i]
        if cktable[key] == 'D2H':
            total_weights = total_d2h_traffic + total_weights
            avg_bw = avg_bw + bw.iloc[i] * float(total_d2h_traffic)/total_weights 
            bw_d2h = bw.iloc[i]
        if cktable[key] == 'P2P':
            total_weights = total_p2p_traffic + total_weights
            avg_bw = avg_bw + bw.iloc[i] * float(total_p2p_traffic)/total_weights  
            bw_p2p = bw.iloc[i]

    print_title("Summary of Comm.")
    print("Averaged Achieved H2D Bandwidth: %.1f (GB/s)" % bw_h2d)
    print("Averaged Achieved D2H Bandwidth: %.1f (GB/s)" % bw_d2h)
    print("Averaged Achieved P2P Bandwidth: %.1f (GB/s)" % bw_p2p)
    print("MeasuredTotalTraffic : %lf (MB)" % total_traffic)
    print("MeasuredTotalH2DTraffic : %lf (MB)" % total_h2d_traffic)
    print("MeasuredTotalD2HTraffic : %lf (MB)" % total_d2h_traffic)
    print("MeasuredTotalP2PTraffic : %lf (MB)" % total_p2p_traffic)
    
    accum = np.zeros((1+n_gpus, 1+n_gpus))
    accum_count = np.zeros((1+n_gpus, 1+n_gpus))
    accum_time = np.zeros((1+n_gpus, 1+n_gpus))
    
    
    for i in range(len(df_gpu)):
        if df_gpu.loc[i,'copyKind'] == -1 or df_gpu.loc[i,'copyKind'] == 8:
            continue
        src = df_gpu.loc[i,'pkt_src']
        dst = df_gpu.loc[i,'pkt_dst']
        payload = df_gpu.loc[i,'payload']
        accum[src][dst] = int(accum[src][dst] + payload)
        accum_count[src][dst] = int(accum_count[src][dst] + 1)
        if cfg['enable_verbose'] == "true":
            if df_gpu.loc[i,'copyKind'] == 1:
                print("[H2D] HOST%d to GPU%d, count:%d\tpayload:%d\taccum_payload:%d" % ( df_gpu.loc[i,'pkt_src'],df_gpu.loc[i,'pkt_dst'], accum_count[src][dst], payload, accum[src][dst]))
            if df_gpu.loc[i,'copyKind'] == 2:
                print("[D2H] GPU%d to HOST%d, count:%d\tpayload:%d\taccum_payload:%d" % ( df_gpu.loc[i,'pkt_src'],df_gpu.loc[i,'pkt_dst'], accum_count[src][dst], payload, accum[src][dst]))
            if df_gpu.loc[i,'copyKind'] == 10:
                print("[P2P] GPU%d to GPU%d: count:%d\tpayload:%d\taccum_payload:%d" % ( df_gpu.loc[i,'pkt_src'],df_gpu.loc[i,'pkt_dst'], accum_count[src][dst], payload, accum[src][dst]))


    for i in xrange(accum_time.shape[0]):
        accum_time[0][i] = accum[0][i]/(1024.0*1024*1024)/bw_h2d
        accum_time[i][0] = accum[i][0]/(1024.0*1024*1024)/bw_d2h
        for j in xrange(accum_time.shape[1]):
            if i>0 and j>0:
                accum_time[i][j] = accum[i][j]/(1024.0*1024*1024)/bw_p2p
    
    
    print("Traffic Matrix (log10(B)):")
    row_str = "\tHOST\t" 
    for i in range(1,accum.shape[1]):
            row_str = row_str + "GPU%d"%i + "\t"
    print(row_str)
    for i in range(accum.shape[0]):
        if i == 0:
            row_str = "HOST\t"
        else:
            row_str = "GPU%d\t"%i
        for j in range(accum.shape[1]):
            row_str = row_str + "%d"%(int(np.log10(1+accum[i][j]))) + "\t"
        print(row_str)

    print("Traffic Matrix (MB):")
    row_str = "\tHOST\t" 
    for i in range(1,accum.shape[1]):
            row_str = row_str + "GPU%d"%i + "\t"
    print(row_str)
    for i in range(accum.shape[0]):
        if i == 0:
            row_str = "HOST\t"
        else:
            row_str = "GPU%d\t"%i
        for j in range(accum.shape[1]):
            row_str = row_str + "%d"%(accum[i][j]/(1024*1024)) + "\t"
        print(row_str)


    print("Traffic Time Matrix (s):")
    row_str = "\tHOST\t" 
    for i in range(1,accum_time.shape[1]):
            row_str = row_str + "GPU%d"%i + "\t"
    print(row_str)
    for i in range(accum_time.shape[0]):
        if i == 0:
            row_str = "HOST\t"
        else:
            row_str = "GPU%d\t"%i
        for j in range(accum_time.shape[1]):
            row_str = row_str + "%.3lf"%(accum_time[i][j]) + "\t"
        print(row_str)

    
    print("MeasuredMaxCommStreamTime : %lf (MB)" % np.max(accum_time))

    df_gpu.to_csv(logdir+'/'+'comm.csv', columns =  ["timestamp", "pkt_src", "pkt_dst", "payload","bandwidth"] )    


def gpu_profile(cfg, df_gpu):
    total_kernel_time = 0.0
    total_gpu_time = 0.0 
    top_k = int(cfg['top_k'])
    
    num_gpus = 0
    with open( logdir + 'CUDAPROC0_CUPTI_ACTIVITY_KIND_DEVICE.csv') as f:
        num_gpus = len(f.readlines())-1
        print("Number of GPUs = %d" % num_gpus )
    
    print_title("Task Time (MEMCPY included) for each Device (s)")
    grouped_df = df_gpu.groupby("deviceId")["duration"]
    total_tasktime = 0
    for key, item in grouped_df:
        print("[%d]: %lf" % (int(float(key)), grouped_df.get_group(key).sum()))
        total_tasktime = total_tasktime + grouped_df.get_group(key).sum()
    n_devices = len(grouped_df)
    per_gpu_time = total_tasktime / n_devices
    print("Averaged GPU time of devices: %.2lf" % per_gpu_time)

    print_title("Data Traffic (bidirection) for each Device (MB)")
    grouped_df = df_gpu.groupby("deviceId")["payload"]
    for key, item in grouped_df:
        print("[%d]: %lf" % (key, grouped_df.get_group(key).sum() / 1000000.0))


    grouped_df = df_gpu.groupby("copyKind")["duration"]
    for key, item in grouped_df:
        if key == -1:
            total_kernel_time = grouped_df.get_group(key).sum()

    print_title("All-reduce Time (s)")
    all_reduce_time=0
    grouped_df = df_gpu.groupby("name")["duration"]
    for key, item in grouped_df:
        #print("[%s]: %lf" % (key, grouped_df.get_group(key).sum()))
        if key.find("AllReduce") != -1:
            all_reduce_time = all_reduce_time +  grouped_df.get_group(key).sum()
                

    if cfg['enable_verbose'] == "true":
        print_title("Data Traffic for Each Pair of deviceId and CopyKind (MB)")
        devcopy = grouped_df = df_gpu.groupby(["deviceId", "copyKind"])[
            "payload"].sum() / 1000000
        print(devcopy)
        print_title(
            "Data Communication Time for Each Pair of deviceId and CopyKind (s)")
        devcopytime = grouped_df = df_gpu.groupby(
            ["deviceId", "copyKind"])["duration"].sum()
        print(devcopytime)

    print_title("Task Time spent on Each Stream (s)")
    grouped_df = df_gpu.groupby("pid")["duration"]
    

    s = []
    for key, item in grouped_df:
        s.append( [key, grouped_df.get_group(key).sum()] )
    topk_streams = sorted(s,key=lambda l:l[1], reverse=True)[:-top_k]
    for s in topk_streams:   
        print("[%d]: %.3lf" % (s[0],s[1]))
    print("Mean of Top-%d Stream Times = %.2lf" %
          (len(topk_streams), np.mean(topk_streams)))


    comm_profile(cfg, df_gpu)
    print("MeasuredTotalKernelTime : %lf (s)" % total_kernel_time)
    
    print_title("Summary of Kernels")
    print("MeasuredTotalKernelTime : %lf (s)" % total_kernel_time)
    print("MeasuredAllReduceTime : %lf (s)" % all_reduce_time)


    if enable_overlapness:
        print_title("Overlapness for All Events (s)")
        events = []
        for i in range(len(df_gpu)):
            t_begin = df_gpu.iloc[i]['timestamp']
            d = df_gpu.iloc[i]['duration']
            t_end = t_begin + d
            e = Event(i, 0, t_begin, d)
            events.append(e)
            e = Event(i, 1, t_end, d)
            events.append(e)
        # for i in range(3):
        # print("df_gpu[%d]=%lf" % (i,df_gpu.iloc[i]['timestamp']))
        #    t_begin =   i
        #    d = 0.5 * random.randint(1, 10)
        #    t_end = t_begin + d
        #    e = Event(i, 0, t_begin, d)
        #    events.append(e)
        #    e = Event(i, 1, t_end, d)
        #    events.append(e)
        events.sort(key=attrgetter('timestamp'))

        event_stack = []
        overlaptime = 0
        for e in events:
            # print(event_stack)
            if e.ttype == 0:
                event_stack.append(e)
            if e.ttype == 1:
                # print("reach end of time for event-%d" % (e.name))
                # find all the previous event with
                for es in event_stack:
                    if es.name != e.name:
                        # print("n:%d t:%lf d:%lf overlaptime:%lf" % (es.name,
                        # es.timestamp, es.duration, overlaptime))
                        overlaptime = overlaptime + overlap(
                            es.timestamp,
                            es.timestamp + es.duration,
                            e.timestamp - e.duration,
                            e.timestamp)
                # print("pop out %d" % e.name)
                event_stack = [es for es in event_stack if es.name != e.name]
        print("Measured Overlapped time of Events: %lf" % (overlaptime))

def net_profile(cfg, df):
    print_title("Network Profiling: Communication Time (s)")
    grouped_df = df.groupby("name")["duration"]
    total_net_time = 0
    n_packets = 0 
    for key, item in grouped_df:
        #print("[%s]: %lf" % (key, grouped_df.get_group(key).sum()))
        if key.find("network:tcp:") != -1:
            total_net_time = total_net_time + grouped_df.get_group(key).sum()
            n_packets = n_packets + 1
    print("total network time = %.3lf" % total_net_time)
    print("total amount of network packets  = %d" % n_packets)

def cpu_profile(cfg, df):
    print_title("CPU Profiling: Task Time (IO included) for each Cores (s)")
    grouped_df = df.groupby("deviceId")["duration"]
    total_exec_time = 0
    for key, item in grouped_df:
        if cfg['enable_verbose'] == "true":
            print("[%d]: %lf" % (key, grouped_df.get_group(key).sum()))
        total_exec_time = total_exec_time + grouped_df.get_group(key).sum()
    n_devices = len(grouped_df)
    avg_exec_time = total_exec_time / n_devices
    print("total execution time = %.3lf" % total_exec_time)
    print("average execution time across devices = %.3lf" % avg_exec_time)

class ProfiledDomainDNN:
    domain_name = "DNN"
    prefix = "[ProfiledDomain%s]\t" % domain_name
    def __init__(self):
        self.name = "general"
        self.batch_size = 64
        self.iterations = 21
        self.throughput = 1
        self.avg_cpu_time = 1
    def get_batch_size(self,filepath):
        with open(filepath) as f:
            lines = f.readlines()
            for line in lines:
                pos = line.find("--batch_size")
                if pos >= 0:
                    self.batch_size = int(line[pos:].split()[0].split('=')[1])
                    print(self.prefix + "batch_size: %d" % self.batch_size)
                    break 
    
    def get_iterations(self,filepath):
        with open(filepath) as f:
            lines = f.readlines()
            for line in lines:
                pos = line.find("--num_batches") 
                if pos >= 0:
                    self.iterations = int(line[pos:].split()[0].split('=')[1]) + 11
                    print( self.prefix + "iterations: %d" % self.iterations)
                    break 
    
    def get_throughput(self,filepath):
        with open(filepath) as f:
            lines = f.readlines()
            for line in lines:
                if line.find("total images/sec:") != -1:
                    self.throughput = float(line.split()[2])
                    print( self.prefix + "Throughput: %.2lf" % self.throughput)
                    break 

if __name__ == "__main__":
    print('Number of arguments: %d arguments' % len(sys.argv))
    print('Argument List: %s' % str(sys.argv))
    logdir = []
    filein = []
    enable_verbose = False
    enable_overlapness = False
    df_gpu = []
    df_cpu = []

    parser = argparse.ArgumentParser(description='SOFA Analyze')
    parser.add_argument(
        "--logdir",
        metavar="/path/to/logdir/",
        type=str,
        required=False,
        help='path to the directory of SOFA logged files')
    parser.add_argument(
        '--config',
        metavar="/path/to/config.cfg",
        type=str,
        required=False,
        help='path to the directory of SOFA configuration file')



    args = parser.parse_args()
    logdir = "./sofalog/" 
    filein_config = "./sofa.cfg"
    filein_gpu = logdir + "gputrace.csv"
    filein_cpu = logdir + "cputrace.csv"
  
    if args.logdir != None:
        args.logdir = args.logdir

    if args.config != None:
        args.config = args.config


    cfg = read_config(filein_config)


    try:
        df_cpu = pd.read_csv(filein_cpu)
        cpu_profile(cfg, df_cpu)
        net_profile(cfg, df_cpu)
    except IOError:
        print_warning(
            "cputrace.csv is not found")
        quit()
    
    try:
        df_gpu = pd.read_csv(filein_gpu)
        df_gpu.loc[:,'timestamp'] -= df_gpu.loc[0,'timestamp']
        gpu_profile(cfg, df_gpu)
        
    except IOError:
        print_warning(
            "gputrace.csv is not found. If there is no need to profile GPU, just ignore it.")

    
