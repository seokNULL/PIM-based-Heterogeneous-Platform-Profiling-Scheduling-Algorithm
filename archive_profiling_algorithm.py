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

def update_path_table(idx, path_len, nextPath):
    start_idx = idx - path_len + 1
    register_current_edge_set = False
    if not pathTable:
        pathTable[tuple(current_edge_set)] = (start_idx, nextPath) 
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
        pathTable[tuple(current_edge_set)] = (start_idx, nextPath)   

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

# print(pathTableQueue)
for key, value in pathTableQueue.items():
    print(key)
    print(value)

def update_global_path_table(pathTable):
    current_edge_set = list(pathTable.keys())
    print("\nPath Table")
    print(pathTable)
    register_current_edge_set = False
    add_flag = True
    current_edge_list = []
    for edge_set in pathTable.keys():
        # current_edge_list.append(list(edge_set))
        # current_edge_list = list(edge_set)
        current_edge_list.append(edge_set)
    print("Current edge list: ", current_edge_list)
    register_edge_set = False

    if not globalPathList:
        print("Initalize global path.")
        globalPathList.extend(current_edge_list)
        # print("List: ", globalPathList)
    else:
        # prev_edge_list = []
        # for item in globalPathList:
        #     prev_edge_list.append(item)
        # print("prev_edge_list: ", prev_edge_list)
        # print("globalPathList: ", globalPathList)
        add_list = []
        remove_list = []
        already_checked = []
        for prev_item in globalPathList:
            print("prev edge: ", prev_item)
            for cur_item in current_edge_list:
                print("\nNew edge: ", cur_item)
                if set(cur_item).issubset(set(prev_item)):
                    print("\nCurrent edge is subset of previous edges")
                    register_current_edge_set = False
                    if cur_item in add_list:
                        add_list.remove(cur_item)
                    if cur_item not in already_checked:
                        already_checked.append(cur_item)
                    continue
                else:
                    # print(set(prev_item), set(cur_item))
                    # print(set(prev_item) - set(cur_item))
                    if set(cur_item).issuperset(set(prev_item)):
                        print("\nCurrent edge is superset of previous edges")
                        print("add_list: ", add_list)
                        print("remove_list: ", remove_list)
                        if cur_item not in add_list:
                            print("Add ", cur_item, " to add_list.")
                            add_list.append(cur_item)
                        if prev_item not in remove_list:
                            print("Remove ", cur_item, " to remove_list.")
                            remove_list.append(prev_item)
                        register_current_edge_set = True
                    else:
                        print("\nNew edge is superset of previous edges")
                        if cur_item not in remove_list and cur_item not in already_checked:
                            if cur_item not in add_list:
                                add_list.append(cur_item)

        # print("remove_list: ")
        # print(remove_list)
        # print("add_list")
        # print(add_list)

        for item1 in remove_list:
            globalPathList.remove(item1)
        for item2 in add_list:
            globalPathList.append(item2)
        # print(globalPathList)

        # for global_edge in globalPathList:
        #     if global_edge in 

globalPathList = []
for idx, pathTable in pathTableQueue.items():
    print("Path table: ", pathTable)
    update_global_path_table(pathTable)
    print(globalPathList)
end2 = time.time()
print("Elapsed: ", end2 - start)