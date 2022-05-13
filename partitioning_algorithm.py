import os
import json
from dataclasses import dataclass
import copy
import time

@dataclass
class Datafield:
    sink_ptr: tuple
    size: int
    sink_next_ptr: []
    src_ptr: tuple
    src_next_ptr: []
    color : str
    edge_list : []

NUM_OF_NODES = 0 
NUM_OF_DEVICES = 2
prof_data = {}

pim_op_list = []
cpu_prof = os.path.join('cpu_roberta.json')
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


pim_prof = os.path.join('pim_roberta.json')
with open(pim_prof, 'r') as f:
    data = json.load(f)
    for item in data:
        if (item['name'].find('_kernel_time') != -1):
            node_name = item['name'].replace('_kernel_time', '')
            ep_type = item['args']['provider'].replace('ExecutionProvider', '').lower()
            if node_name in prof_data.keys() and ep_type == 'pim':
                pim_op_list.append(node_name)

print(pim_op_list)

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
                edge_dict[edge] = [edge_attr, 'white']
            if pim_src_nodes:
                if (pim_src_nodes[0], 1) not in source_list:
                    DCG[cur_node][dev_idx].src_ptr = (pim_src_nodes[0], 1)
                    # Add to edge_dict
                    edge = ((pim_src_nodes[0], 1), (cur_node, dev_idx))
                    edge_attr = (1, dev_idx, attr['elem_size'])
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
                    edge_dict[edge] = [edge_attr, 'white']                              
                if src_nodes:
                    if (src_nodes[0], 0) not in source_list:
                        source_list.append((src_nodes[0], 0))
                         # Add to edge_dict
                        edge = ((src_nodes[0], 0), (cur_node, dev_idx))
                        edge_attr = (0, dev_idx, attr['elem_size'])
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
                                edge_dict[edge] = [edge_attr, 'white']
                                DCG[cur_node][dev_idx].src_next_ptr.append(src_data_field)  

# DMA size, color

# print("EDGE DICT")
# print(edge_dict)
# for key, value in DCG.items():
#     print(key)
#     # print(value)
#     for val in value:
#         print(val)
#     print("\n")

edge_list = []
for key, value in edge_dict.items():
    print(key, '\t\t\t\t', value)
    print("\n")
    if value not in edge_list:
        edge_list.append(value)

print(edge_list)

dcg_node_list = list(DCG.keys())
node_list = list(prof_data.keys())
# print(dcg_node_list[0])
#DFS
root = (dcg_node_list[0], 0)
stack = [root]

node_cnt = 0

while stack:
    # print("BEFORE STACK: ", stack)
    u = stack[-1]
    # print("Pop: ", u)
    if not u[0] == dcg_node_list[-1]:
        v_idx = dcg_node_list.index(u[0]) + 1
        dev_idx = 0
        for v in DCG[dcg_node_list[v_idx]]:
            if v.color is None:
                pass
            else:
                adj = (dcg_node_list[v_idx], dev_idx)
                if v.color is 'white':
                    v.color = 'grey'
                    for prev in stack:
                        edge = (prev, adj)
                        if edge in edge_dict:
                            edge_dict[edge][1] = 'black'
                    # print("Visit: ", adj)
                    stack.append(adj)
                else:
                    # if edges are black
                    is_edge_all_black = True
                    for key, value in edge_dict.items():
                        if key[1] == adj:
                            if value[1] == 'white':
                                is_edge_all_black = False
                                break
                    if is_edge_all_black:
                        stack.pop()
                        # print("Finish: ", adj)
                        v.color = 'black'
                    
            dev_idx += 1
    else:
        print("REACHED THE END")
        stack.pop()
        # print("Finish: ", adj)
        v.color = 'black'        
    node_cnt += 1
    # print("AFTER STACK: ", stack)

    # print(edge_dict)
    # if DCG[dcg_node_list[v_idx]][dev_idx] is None:
    #     dev_idx = 1 - dev_idx
# edge_list = []
# for key, value in edge_dict.items():
#     print(key, '\t\t\t\t', value)
#     print("\n")
#     if value not in edge_list:
#         edge_list.append(value)

# print(edge_list)



# print(edge_dict)

    # if u.sink_ptr and DCG[u.sink_ptr[0]][u.sink_ptr[1]] == 'white':

# for key, value in edge_dict.items():
#     print(key,'\t\t\t', value)

# (node, dev) -> (node, dev)


# for cur_node, attr in prof_data.items():
#     print(cur_node)
#     # print(attr['graph_index'])
#     print(attr)
#     print("\n")

# path = []
# stack = [prof_data.keys()[0]]

# while (len(stack) != 0):
#     s = stack.pop()
#     if s not in path:
#         path.append(s)
# print(path)

# ## Check shape
# for key, data in DCG.items():
#     # print(key, data)
#     print("key: ", key)
#     # print("data: ", data)
#     for data_field in data:
#         print(data_field)
#     print("\n")

# def isNeighborCutVertex(max_idx, dnn_idx):
#     if dnn_idx == len(dcg_node_list) - 1:
#         return True
#     else:
#         if dcg_node_list[dnn_idx + 1] in pim_op_list:
#             return False
#         else:
#             if dnn_idx + 1 > max_idx:
#                 return True
#             else:
#                 return False

# def get_path(num, path_len, number_system):
#     if number_system == 1 or num == 0:
#         return '0' * path_len
#     else:
#         nums = []
#         while num:
#             num, r = divmod(num, number_system)
#             nums.append(str(r))
#         result = ''.join(reversed(nums))
#         if len(result) < path_len:
#             result =  '0'*(path_len-len(result)) + result
#         return result

# def remove_edge(dnn_idx, dev_idx):
#     # print("REMOVE")
#     # if dcg_node_list[dnn_idx] == 'START' or 'END':
#     #     return
#     currentNode = DCG[dcg_node_list[dnn_idx]][dev_idx]
#     if currentNode.src_ptr is not None:
#         src_node, src_dev = currentNode.src_ptr
#         data_size = DCG[src_node][src_dev].size
#         edge = str(data_size) + str(src_dev) + str(dev_idx)
#         # print("edge: ", edge)
#         if edge in current_edge_dict.keys():
#             current_edge_dict[edge] -= 1
#             if current_edge_dict[edge] == 0:
#                 del current_edge_dict[edge]
#     if currentNode.src_next_ptr is not None:
#         for j in range(len(currentNode.src_next_ptr)):
#             src_node, src_dev = currentNode.src_next_ptr[j].src_ptr
#             data_size = DCG[src_node][src_dev].size
#             edge = str(data_size) + str(src_dev) + str(dev_idx)
#             # print("edge: ", edge)
#             if edge in current_edge_dict.keys():
#                 current_edge_dict[edge] -= 1
#                 if current_edge_dict[edge] == 0:
#                     del current_edge_dict[edge]            

# def update_path_table(idx, path_len, nextPath):
#     start_idx = idx - path_len + 1
#     register_current_edge_set = False
#     if not pathTable:
#         pathTable[tuple(current_edge_set)] = (start_idx, nextPath) 
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
#         pathTable[tuple(current_edge_set)] = (start_idx, nextPath)          

# def updateMaxIdx(max_idx, idx):
#     dnn_node = dcg_node_list[idx]
#     for dev_idx in range(NUM_OF_DEVICES):
#         if DCG[dnn_node][dev_idx].sink_next_ptr:
#             last_sink_node, last_sink_dev = DCG[dnn_node][dev_idx].sink_ptr
#             if node_list.index(last_sink_node) > max_idx:
#                 max_idx = node_list.index(last_sink_node)
#     return max_idx

# def update_edge(dnn_idx, dev_idx):
#     # print("Update")
#     # if dcg_node_list[dnn_idx] == 'START' or dcg_node_list[dnn_idx] == 'END':
#     #     return
#     currentNode = DCG[dcg_node_list[dnn_idx]][dev_idx]
#     if currentNode.src_ptr is not None:
#         src_node, src_dev = currentNode.src_ptr
#         data_size = DCG[src_node][src_dev].size
#         edge = str(data_size) + str(src_dev) + str(dev_idx)
#         # print("edge: ", edge)
#         if edge not in current_edge_dict.keys():
#             current_edge_dict[edge] = 1
#         else:
#             current_edge_dict[edge] += 1            
#     if currentNode.src_next_ptr is not None:
#         for j in range(len(currentNode.src_next_ptr)):
#             src_node, src_dev = currentNode.src_next_ptr[j].src_ptr
#             data_size = DCG[src_node][src_dev].size
#             edge = str(data_size) + str(src_dev) + str(dev_idx)
#             # print("edge: ", edge)
#             if edge not in current_edge_dict.keys():
#                 current_edge_dict[edge] = 1
#             else:
#                 current_edge_dict[edge] += 1  


# dcg_node_list = list(DCG.keys())

# num = 0
# path_len = 1
# idx = 0
# max_idx = 0
# # print(len(dcg_node_list))
# current_edge_dict = {}
# distinctEdgeSet = set()
# pathTableQueue = {}
# pathTableCnt = 0
# max_entry_size = 0
# max_path_len = 0
# start = time.time()

# while True:
#     max_num = pow(NUM_OF_DEVICES, path_len) - 1
#     # print("Current node: ", dcg_node_list[idx])
#     if idx == len(dcg_node_list) or isNeighborCutVertex(max_idx, idx):
#         if idx == len(dcg_node_list):
#             break
#         pathTable = {}
#         if path_len == 1:
#             pass
#         else:
#             while num != max_num:
#                 max_path_len = max(max_path_len, path_len)
#                 # print("max_num, num: ", max_num, num)
#                 currentPath = get_path(num, path_len, NUM_OF_DEVICES)
#                 # print(currentPath)
#                 currentNum = num
#                 num += 1
#                 nextPath = get_path(num, path_len, NUM_OF_DEVICES)
#                 # print("\ncurrentPath: ", currentPath)
#                 # print("nextPath: ", nextPath)
#                 backTrackIdx = currentNum ^ num
#                 # print("backtrack: ", get_path(backTrackIdx, path_len, NUM_OF_DEVICES))
#                 exclude_indices = get_path(currentNum & backTrackIdx, path_len, NUM_OF_DEVICES)
#                 include_indices = get_path(num & backTrackIdx, path_len, NUM_OF_DEVICES)
#                 changed_indices = get_path(backTrackIdx, path_len, NUM_OF_DEVICES)
#                 # print("exclude_indices: ", exclude_indices)
#                 for i in range(len(exclude_indices)):
#                     dnn_idx = idx - path_len + 1 + i
#                     if changed_indices[i] == '1':
#                         # print(currentPath[i])
#                         dev_idx = int(currentPath[i])
#                         remove_edge(dnn_idx, dev_idx)
#                 # print("include_indices: ", include_indices)
#                 for i in range(len(include_indices)):
#                     dnn_idx = idx - path_len + 1 + i
#                     if changed_indices[i] == '1':
#                         # print(nextPath[i])
#                         dev_idx = int(nextPath[i])
#                         update_edge(dnn_idx, dev_idx)
#                 current_edge_set = set(current_edge_dict.keys())
#                 distinctEdgeSet.update(current_edge_set)
#                 update_path_table(idx, path_len, nextPath)    
#             if pathTable:        
#                 pathTableQueue[str(pathTableCnt)] = pathTable
#                 max_entry_size = max(max_entry_size, len(pathTable.keys()))
#                 pathTableCnt += 1
#         num = 0
#         path_len = 1
#         max_idx = 0
#         current_edge_dict = {}
#         pathTable = {}
#     else:
#         path_len += 1
#         path = get_path(num, path_len, NUM_OF_DEVICES)
#         max_idx = updateMaxIdx(max_idx, idx)
#     idx += 1
# end = time.time()

# print("Length: ")
# print(len(pathTableQueue))
# print("Elapsed: ", end - start)
# print("M: ", max_path_len)
# print("L: ", max_entry_size)

# DFS on DCG

