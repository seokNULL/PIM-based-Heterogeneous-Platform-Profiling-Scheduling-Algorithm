import json
import os
from dataclasses import dataclass
from statistics import median
import time

cpu_profile_file = 'cpu_roberta.json'
pim_profile_file = 'pim_roberta.json'


@dataclass
class Datafield:
    sink_ptr: tuple
    size: int
    sink_next_ptr: []
    src_ptr: tuple
    src_next_ptr: []
    color : str
    edge_list : []

@dataclass
class Cost:
    node_cost: int
    edge_cost: int

NUM_OF_NODES = 0 
NUM_OF_DEVICES = 2
prof_data = {}

# BUILD DCG
pim_op_list = []
cpu_prof = os.path.join(cpu_profile_file)
with open(cpu_prof, 'r') as f:
    data = json.load(f)
    for item in data:
        if (item['name'].find('_kernel_time') != -1):
            node_name = item['name'].replace('_kernel_time', '')

            op_name = item['args']['op_name']
            ep_type = item['args']['provider'].replace('ExecutionProvider', '').lower()

            prof_data[node_name] = {}
            prof_data[node_name]['op_kind'] = op_name
            prof_data[node_name]['ep_type'] = ep_type
            prof_data[node_name]['graph_index'] = int(item['args']['graph_index'])
            # Output size / sizeof(float)
            prof_data[node_name]['elem_size'] = int(int(item['args']['output_size']) / 4)
            incoming_nodes = item['args']['input_nodes'].split()
            outgoing_nodes = item['args']['output_nodes'].split() 

            prof_data[node_name]['src_nodes'] = incoming_nodes
            prof_data[node_name]['sink_nodes'] = outgoing_nodes

            NUM_OF_NODES += 1

# print("PROFILE DATA")
# for key, value in prof_data.items():
#     print(key)
#     print(value)
#     print("\n")

# Collect pim only
pim_prof = os.path.join(pim_profile_file)
with open(pim_prof, 'r') as f:
    data = json.load(f)
    for item in data:
        if (item['name'].find('_kernel_time') != -1):
            node_name = item['name'].replace('_kernel_time', '')
            ep_type = item['args']['provider'].replace('ExecutionProvider', '').lower()
            if node_name in prof_data.keys() and ep_type == 'pim':
                pim_op_list.append(node_name)

# print("PIM OP LIST")
# print(pim_op_list)

empty_datafield = Datafield(sink_ptr=None, size=None, sink_next_ptr=None, src_ptr=None, src_next_ptr=None, color=None, edge_list=None)
node_list = list(prof_data.keys())

DCG = {}
dev_list = ["cpu", "pim"]
for node_name in prof_data.keys():
    DCG[node_name] = [None] * NUM_OF_DEVICES
    for k in range(NUM_OF_DEVICES):
        if k == 0:
            DCG[node_name][k] = Datafield(None, None, None, None, None, 'white', [])
        else:
            DCG[node_name][k] = Datafield(None, None, None, None, None, None, None)

edge_dict = {}
source_list = []
for cur_node, attr in prof_data.items():
    print("Current node: ", cur_node)
    sink_nodes = attr['sink_nodes'][:]
    src_nodes = attr['src_nodes'][:]
    for dev in dev_list:
        dev_idx = dev_list.index(dev)
        # 1. CPU device
        if dev_idx == 0:
            pim_sink_nodes = [x for x in sink_nodes if x in pim_op_list]
            pim_src_nodes = [x for x in src_nodes if x in pim_op_list]
            if pim_sink_nodes:
                DCG[cur_node][dev_idx].sink_ptr = (pim_sink_nodes[0], 1)
                DCG[cur_node][dev_idx].size = attr['elem_size']
                DCG[cur_node][dev_idx].color = 'white'
                DCG[cur_node][dev_idx].edge_list = []
                # Add to edge_dict
                edge = ((cur_node, dev_idx), (pim_sink_nodes[0], 1))
                edge_attr = (dev_idx, 1, attr['elem_size'])
                print(edge_attr)
                edge_dict[edge] = [edge_attr, 'white']
            if pim_src_nodes:
                if (pim_src_nodes[0], 1) not in source_list:
                    DCG[cur_node][dev_idx].src_ptr = (pim_src_nodes[0], 1)
                    # Add to edge_dict
                    edge = ((pim_src_nodes[0], 1), (cur_node, dev_idx))
                    edge_attr = (1, dev_idx, attr['elem_size'])
                    print(edge_attr)
                    edge_dict[edge] = [edge_attr, 'white']
                    source_list.append((pim_src_nodes[0], 1))
                if len(pim_src_nodes) > 1:
                    DCG[cur_node][dev_idx].src_next_ptr = []
                    for i in range(1, len(pim_src_nodes)):
                        src_data_field = Datafield(None, None, None, None, None, 'white', [])
                        if (pim_src_nodes[i], 1) not in source_list:
                            source_list.append((pim_src_nodes[i], 1))
                            src_data_field.src_ptr = (pim_src_nodes[i], 1)
                            # Add to edge_dict
                            edge = ((pim_src_nodes[i], 1), (cur_node, dev_idx))
                            edge_attr = (1, dev_idx, attr['elem_size'])
                            print(edge_attr)
                            edge_dict[edge] = [edge_attr, 'white']
                            DCG[cur_node][dev_idx].src_next_ptr.append(src_data_field)                            
        # 2. PIM device
        else:
            if cur_node not in pim_op_list:
                continue
            else:
                DCG[cur_node][dev_idx].color = 'white'
                DCG[cur_node][dev_idx].edge_list = []                
                if sink_nodes:
                    DCG[cur_node][dev_idx].sink_ptr = (sink_nodes[0], 0)
                    DCG[cur_node][dev_idx].size = attr['elem_size']
                    # DCG[cur_node][dev_idx].color = 'white'
                    # DCG[cur_node][dev_idx].edge_list = []
                    # Add to edge_dict
                    edge = ((cur_node, dev_idx), (sink_nodes[0], 0))
                    edge_attr = (dev_idx, 0, attr['elem_size'])
                    print(edge_attr)
                    edge_dict[edge] = [edge_attr, 'white']                              
                if src_nodes:
                    if (src_nodes[0], 0) not in source_list:
                        source_list.append((src_nodes[0], 0))
                         # Add to edge_dict
                        edge = ((src_nodes[0], 0), (cur_node, dev_idx))
                        edge_attr = (0, dev_idx, attr['elem_size'])
                        print(edge_attr)
                        edge_dict[edge] = [edge_attr, 'white']
                        DCG[cur_node][dev_idx].src_ptr = (src_nodes[0], 0)
                    if len(src_nodes) > 1:
                        DCG[cur_node][dev_idx].src_next_ptr = []
                        for i in range(1, len(src_nodes)):
                            src_data_field = Datafield(None, None, None, None, None, 'white', [])
                            if (src_nodes[i], 0) not in source_list:
                                source_list.append((src_nodes[i], 0))
                                src_data_field.src_ptr = (src_nodes[i], 0)
                                # Add to edge_dict
                                edge = ((src_nodes[i], 0), (cur_node, dev_idx))
                                edge_attr = (0, dev_idx, attr['elem_size'])
                                print(edge_attr)
                                edge_dict[edge] = [edge_attr, 'white']
                                DCG[cur_node][dev_idx].src_next_ptr.append(src_data_field)  
# for key, value in edge_dict.items():
#     print(key)
#     for val in value:
#         print(val)
#     print("\n")

dcg_node_list = list(DCG.keys())

num = 0
path_len = 1
idx = 0
max_idx = 0
current_edge_dict = {}
distinctEdgeSet = set()
pathTableQueue = {}
pathTableCnt = 0
max_entry_size = 0
max_path_len = 0
start = time.time()

def isNeighborCutVertex(max_idx, dnn_idx):
    if dnn_idx == len(dcg_node_list) - 1:
        return True
    else:
        if dcg_node_list[dnn_idx + 1] in pim_op_list:
            return False
        else:
            if dnn_idx + 1 > max_idx:
                return True
            else:
                return False


def get_path(num, path_len, number_system):
    if number_system == 1 or num == 0:
        return '0' * path_len
    else:
        nums = []
        while num:
            num, r = divmod(num, number_system)
            nums.append(str(r))
        result = ''.join(reversed(nums))
        if len(result) < path_len:
            result =  '0'*(path_len-len(result)) + result
        return result

def updateMaxIdx(max_idx, idx):
    dnn_node = dcg_node_list[idx]
    for dev_idx in range(NUM_OF_DEVICES):
        if DCG[dnn_node][dev_idx].sink_next_ptr:
            last_sink_node, last_sink_dev = DCG[dnn_node][dev_idx].sink_ptr
            if node_list.index(last_sink_node) > max_idx:
                max_idx = node_list.index(last_sink_node)
    return max_idx


def update_edge(dnn_idx, dev_idx):
    # print("Update")
    # if dcg_node_list[dnn_idx] == 'START' or dcg_node_list[dnn_idx] == 'END':
    #     return
    currentNode = DCG[dcg_node_list[dnn_idx]][dev_idx]
    if currentNode.src_ptr is not None:
        src_node, src_dev = currentNode.src_ptr
        data_size = DCG[src_node][src_dev].size
        edge = str(data_size) + str(src_dev) + str(dev_idx)
        # print("edge: ", edge)
        if edge not in current_edge_dict.keys():
            current_edge_dict[edge] = 1
        else:
            current_edge_dict[edge] += 1            
    if currentNode.src_next_ptr is not None:
        for j in range(len(currentNode.src_next_ptr)):
            src_node, src_dev = currentNode.src_next_ptr[j].src_ptr
            data_size = DCG[src_node][src_dev].size
            edge = str(data_size) + str(src_dev) + str(dev_idx)
            # print("edge: ", edge)
            if edge not in current_edge_dict.keys():
                current_edge_dict[edge] = 1
            else:
                current_edge_dict[edge] += 1  

def remove_edge(dnn_idx, dev_idx):
    # print("REMOVE")
    # if dcg_node_list[dnn_idx] == 'START' or 'END':
    #     return
    currentNode = DCG[dcg_node_list[dnn_idx]][dev_idx]
    if currentNode.src_ptr is not None:
        src_node, src_dev = currentNode.src_ptr
        data_size = DCG[src_node][src_dev].size
        edge = str(data_size) + str(src_dev) + str(dev_idx)
        # print("edge: ", edge)
        if edge in current_edge_dict.keys():
            current_edge_dict[edge] -= 1
            if current_edge_dict[edge] == 0:
                del current_edge_dict[edge]
    if currentNode.src_next_ptr is not None:
        for j in range(len(currentNode.src_next_ptr)):
            src_node, src_dev = currentNode.src_next_ptr[j].src_ptr
            data_size = DCG[src_node][src_dev].size
            edge = str(data_size) + str(src_dev) + str(dev_idx)
            # print("edge: ", edge)
            if edge in current_edge_dict.keys():
                current_edge_dict[edge] -= 1
                if current_edge_dict[edge] == 0:
                    del current_edge_dict[edge]    

# def update_path_table(idx, path_len, nextPath):
#     start_idx = idx - path_len + 1
#     register_current_edge_set = False
#     if not pathTable:
#         # pathTable[tuple(current_edge_set)] = (start_idx, nextPath) 
#         pathTable[tuple(current_edge_set)] = (start_idx, nextPath, ['white', 0])   
#     else:
#         for edge_set_tuple in list(pathTable.keys()):
#             edge_set = set(edge_set_tuple)
#             if current_edge_set.issubset(edge_set):
#                 register_current_edge_set = False
#                 break
#             else:
#                 if current_edge_set.issuperset(edge_set):
#                     del pathTable[edge_set_tuple]
#                 register_current_edge_set = True
#     if register_current_edge_set:
#         # pathTable[tuple(current_edge_set)] = (start_idx, nextPath)  
#         pathTable[tuple(current_edge_set)] = (start_idx, nextPath, ['white', 0])   

@dataclass
class PTNode:
    start_idx: int
    nextPath: str
    color: str
    edgeCnt: int
    maxEdgeCnt: int
    uaList: set()

def update_path_table(idx, path_len, nextPath):
    start_idx = idx - path_len + 1
    register_current_edge_set = False
    if not pathTable:
        # pathTable[tuple(current_edge_set)] = (start_idx, nextPath) 
        # pathTable[tuple(current_edge_set)] = (start_idx, nextPath, ['white', 0])   
        pathTable[tuple(current_edge_set)] = PTNode(start_idx=start_idx, nextPath=nextPath, color='white', edgeCnt=0, maxEdgeCnt=None, uaList=set())
    else:
        for edge_set_tuple in list(pathTable.keys()):
            edge_set = set(edge_set_tuple)
            if current_edge_set.issubset(edge_set):
                register_current_edge_set = False
                break
            else:
                if current_edge_set.issuperset(edge_set):
                    del pathTable[edge_set_tuple]
                register_current_edge_set = True
    if register_current_edge_set:
        # pathTable[tuple(current_edge_set)] = (start_idx, nextPath)  
        # pathTable[tuple(current_edge_set)] = (start_idx, nextPath, ['white', 0])   
        pathTable[tuple(current_edge_set)] = PTNode(start_idx=start_idx, nextPath=nextPath, color='white', edgeCnt=0, maxEdgeCnt=None, uaList=set())

max_entry_size = 0
max_path_len = 0

while True:
    max_num = pow(NUM_OF_DEVICES, path_len) - 1
    # print("Current node: ", dcg_node_list[idx])
    if idx == len(dcg_node_list) or isNeighborCutVertex(max_idx, idx):
        if idx == len(dcg_node_list):
            break
        pathTable = {}
        if path_len == 1:
            pass
        else:
            while num != max_num:
                max_path_len = max(max_path_len, path_len)
                currentPath = get_path(num, path_len, NUM_OF_DEVICES)
                currentNum = num
                num += 1
                nextPath = get_path(num, path_len, NUM_OF_DEVICES)

                backTrackIdx = currentNum ^ num
                exclude_indices = get_path(currentNum & backTrackIdx, path_len, NUM_OF_DEVICES)
                include_indices = get_path(num & backTrackIdx, path_len, NUM_OF_DEVICES)
                changed_indices = get_path(backTrackIdx, path_len, NUM_OF_DEVICES)
                for i in range(len(exclude_indices)):
                    dnn_idx = idx - path_len + 1 + i
                    if changed_indices[i] == '1':
                        dev_idx = int(currentPath[i])
                        remove_edge(dnn_idx, dev_idx)
                for i in range(len(include_indices)):
                    dnn_idx = idx - path_len + 1 + i
                    if changed_indices[i] == '1':
                        dev_idx = int(nextPath[i])
                        update_edge(dnn_idx, dev_idx)
                current_edge_set = set(current_edge_dict.keys())
                distinctEdgeSet.update(current_edge_set)
                update_path_table(idx, path_len, nextPath)    
            if pathTable:        
                pathTableQueue[str(pathTableCnt)] = pathTable
   
                #pathTable, visited, vertex_cnt
                # pathTableQueue[str(pathTableCnt)] = [pathTable, 'white', 0]
                max_entry_size = max(max_entry_size, len(pathTable.keys()))
                pathTableCnt += 1
        num = 0
        path_len = 1
        max_idx = 0
        current_edge_dict = {}
        pathTable = {}
    else:
        path_len += 1
        path = get_path(num, path_len, NUM_OF_DEVICES)
        max_idx = updateMaxIdx(max_idx, idx)
    idx += 1
end = time.time()

print("M: ", max_path_len)
print("L: ", max_entry_size)

print("distinctEdgeSet")
print(distinctEdgeSet)
# path_len = len(pathTableQueue)
# print("path_len: ", pathTableQueue.keys())
# num = 0
# # ua_edges = edge_dict.keys()
# # print(ua_edges)
ua_edge_list = []
for key, values in edge_dict.items():
    value = values[0]
    attr = str(value[2]) + str(value[0]) + str(value[1])
    if attr not in ua_edge_list:
        ua_edge_list.append(attr)
# print(set(ua_edge_list))
ua_edge_list.remove('201')

ua_edge_set = set(ua_edge_list)
print(ua_edge_list)



##################
###### 0427
##################

# for key, value in pathTableQueue.items():
#     print("\n", key)
#     ua_edge = list(value.keys())
#     for i in range(max_entry_size):
#         if i >= len(ua_edge):
#             continue
#         else:
#             print(ua_edge[i])

global_map = {}
for i in range(max_entry_size):
    global_map[str(i)] = []
    for key, value in pathTableQueue.items():
        ua_edges = list(value.keys())
        if i >= len(ua_edges):
            print("\n", key)
            continue
        else:
            for ua_edge in ua_edges[i]:
                print(ua_edge)
                if ua_edge not in global_map[str(i)]:
                    global_map[str(i)].append(ua_edge)

print(global_map)
"""
# # trackDistinctEdgeSet = set()
# path_info_dict = {}
# max_num = pow(max_entry_size, path_len)
# print(max_num)
# while num != max_num:
#     print(num)
#     currentPath = get_path(num, path_len, max_entry_size)

#     # for i in range(len(currentPath)):
#     #     entry_idx = int(currentPath[i])
#     #     edge_set_tuple = list(pathTableQueue[str(i)].keys())[entry_idx]
#     #     edge_set = set(edge_set_tuple)
#     #     path_info = pathTableQueue[str(i)][edge_set_tuple]
#     #     path_info_dict[num].append(path_info)
#     #     # trackDistinctEdgeSet.update(edge_set)
#     # # if distinctEdgeSet == trackDistinctEdgeSet:
#     # #     break
#     num += 1



# # print(pathTableQueue)
for key in list(pathTableQueue.keys())[:-1]:
    # print(key)
    pathTable = pathTableQueue[key]
    maxEdgeCnt = len(pathTableQueue[str(int(key)+1)].keys())
    for ua_edge, path_info in pathTable.items():
        path_info.maxEdgeCnt = maxEdgeCnt
    # pathTable.maxEdgeCnt = len(pathTableQueue[str(int(key)+1)].keys())
    # print(pathTable)
    # print("\n")
last_key = list(pathTableQueue.keys())[-1]
pathTable = pathTableQueue[last_key]
for ua_edge, path_info in pathTable.items():
    path_info.maxEdgeCnt = 0

# for key in list(pathTableQueue.keys()):
#     pathTable = pathTableQueue[key]
#     print(key)
#     print(pathTable)
#     print("\n")
# # DFS 
# PATH_LEN = len(pathTableQueue.keys())
# path_list = [0] * PATH_LEN
# cnt = 0
# idx = 0
# # stack = [idx]
# stack = [(cnt, idx)]
# flag = 0
# while stack:
#     # cnt = stack[-1]
#     # idx = path_list[cnt]
#     (cnt, idx) = stack[-1]
#     path_list[cnt] = idx
#     print("cnt: ", cnt)
#     print("idx: ", idx)
#     print("stack: ", stack)

#     pt = pathTableQueue[str(cnt)]
#     ua_edge = list(pt.keys())[idx]
#     path_info = pt[ua_edge]
    
#     # all_visited = True

#     if cnt + 1 == PATH_LEN:
#         print("REACHED THE END")
#         # print("PATH LIST: \n", path_list)
#         # all_visited = False
#         print("PATH: ", path_list)
#         path_info.color = 'black'
#         stack.pop()
#     else:
#         next_pt = pathTableQueue[str(cnt + 1)]
#         print("next_pt: ", next_pt)
#         all_visited = True
#         for i in range(path_info.maxEdgeCnt):
#             next_ua_edge = list(next_pt.keys())[i]
#             next_path_info = next_pt[next_ua_edge]
#             print("next_path_info: ", next_path_info)
#             if next_path_info.color == 'white':
#                 next_path_info.color = 'gray'
#                 stack.append((cnt + 1, i))
#                 all_visited = False
#         if all_visited:
#             path_info.color = 'black'
#             stack.pop()            


# DFS ver 2.
PATH_LEN = len(pathTableQueue.keys())
path_list = [0] * PATH_LEN
cnt = 0
idx = 0
# stack = [idx]
stack = [(cnt, idx)]
flag = 0
while stack:
    # cnt = stack[-1]
    # idx = path_list[cnt]
    (cnt, idx) = stack[-1]
    path_list[cnt] = idx
    print("cnt: ", cnt)
    print("idx: ", idx)
    print("stack: ", stack)

    pt = pathTableQueue[str(cnt)]
    ua_edge = list(pt.keys())[idx]
    path_info = pt[ua_edge]
    
    # all_visited = True

    if cnt + 1 == PATH_LEN:
        print("REACHED THE END")
        # print("PATH LIST: \n", path_list)
        # all_visited = False
        print("PATH: ", path_list)
        print("!!!")
        for item in ua_edge:
            print(item)
            path_info.uaList.add(item)
        # path_info.uaList.add(ua_edge_set)
        path_info.color = 'black'
        stack.pop()
    else:
        next_pt = pathTableQueue[str(cnt + 1)]
        print("next_pt: ", next_pt)
        all_visited = True
        for i in range(path_info.maxEdgeCnt):
            next_ua_edge = list(next_pt.keys())[i]
            next_path_info = next_pt[next_ua_edge]
            print("next_path_info: ", next_path_info)
            if next_path_info.color == 'white':
                next_path_info.color = 'gray'
                stack.append((cnt + 1, i))
                all_visited = False
        if all_visited:
            path_info.color = 'black'
            for item in ua_edge:
                print(item)
                path_info.uaList.add(item)
            stack.pop()      

# Apply ALS.

tmp_map = {"def" : [], "undef" : []}
tmp_list = []
for key, value in pathTableQueue.items():
    print(key)
    print(len(value))
    print("\n")
    if len(value) == 1:
        tmp_map["def"].append(key)
        # print(value)
    else:
        print("HHH")
        if len(value) not in tmp_list:
            tmp_list.append(len(value))
        print(len(value))
        tmp_map["undef"].append(key)

print(tmp_list)

# vertex_cnt = 0
# cnt = 0
# idx = 0
# PATH_LEN = len(pathTableQueue.keys())

# path_list = []
# def findPaths(pathTableQueue, start):
#     (cnt, idx) = start
#     print("\nFinding at path table #", cnt)
#     print("idx: ", idx)
#     # vertex_cnt += 1
#     # vertex_list[cnt] = idx;
#     pt = pathTableQueue[str(cnt)]
#     ua_edge = list(pt.keys())[idx]
#     path_info = pt[ua_edge]
#     print("ua_edge: ", ua_edge)
#     print("path_info: ", path_info)
#     path_list.append(ua_edge)
#     path_info.color = 'black'
#     maxEdgeCnt = path_info.maxEdgeCnt
#     # flag = 0
#     if cnt + 1 != PATH_LEN:
#         next_pt = pathTableQueue[str(cnt + 1)]
#         print("next_pt: ", next_pt)
#         for i in range(maxEdgeCnt):
#             print(i, "th neighbor")
#             next_ua_edge = list(next_pt.keys())[i]
#             next_path_info = next_pt[next_ua_edge]
#             if next_path_info.color == 'white':
#                 print("\n\t >> Visit ", i,"th neighbor")
#                 # flag = 1
#                 findPaths(pathTableQueue, (cnt + 1, i))
#     else:
#         print("PATH PRINT")
#         print(path_list)
#         tmp_list = []
#         for item in path_list:
#             for item2 in item:
#                 if item2 not in tmp_list:
#                     tmp_list.append(item2)

#         new_set = set(tmp_list)
#         print("new_set: :", new_set)
#         print("ua_edge_set: :", ua_edge_set)


#     path_info.color = 'white'
#     path_list.pop()

# findPaths(pathTableQueue, (0, 0))
"""