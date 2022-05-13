import os
import json
from dataclasses import dataclass
import copy
import timeit


@dataclass
class Datafield:
    sink_ptr: tuple
    size: int
    sink_next_ptr: []
    src_ptr: tuple
    src_next_ptr: []

NUM_OF_NODES = 0 
NUM_OF_DEVICES = 2
prof_data = {}
# pim_op_list = ["Add_20","Add_22","Add_33","Add_37","Add_35","Add_51","Add_99","Add_100","Add_111","Add_113","Add_123","Add_124","Add_135","Add_139","Add_137","Add_153","Add_201","Add_202","Add_213","Add_215","Add_225","Add_226","Add_237","Add_241","Add_239","Add_255","Add_303","Add_304","Add_315","Add_317","Add_327","Add_328","Add_339","Add_343","Add_341","Add_357","Add_405","Add_406","Add_417","Add_419","Add_429","Add_430","Mul_32","Mul_110","Mul_119","Mul_134","Mul_212","Mul_221","Mul_236","Mul_314","Mul_323","Mul_338","Mul_416","Mul_425","MatMul_36","MatMul_34","MatMul_50","MatMul_98","MatMul_112","MatMul_122","MatMul_138","MatMul_136","MatMul_152","MatMul_200","MatMul_214","MatMul_224","MatMul_240","MatMul_238","MatMul_254","MatMul_302","MatMul_316","MatMul_326","MatMul_342","MatMul_340","MatMul_356","MatMul_404","MatMul_418","MatMul_428"]
pim_op_list = ["Add_20","Add_22","Add_33","Add_37","Add_35","Add_51","Add_99","Add_100","Add_111","Add_113","Add_123","Add_124","Add_135","Add_139","Add_137","Add_153","Add_201","Add_202","Add_213","Add_215","Add_225","Add_226","Add_237","Add_241","Add_239","Add_255","Add_303","Add_304","Add_315","Add_317","Add_327","Add_328","Add_339","Add_343","Add_341","Add_357","Add_405","Add_406","Add_417","Add_419","Add_429","Add_430","Mul_32","Mul_110","Mul_119","Mul_134","Mul_212","Mul_221","Mul_236","Mul_314","Mul_323","Mul_338","Mul_416","Mul_425","MatMul_36","MatMul_34","MatMul_50","MatMul_98","MatMul_112","MatMul_122","MatMul_138","MatMul_136","MatMul_152","MatMul_200","MatMul_214","MatMul_224","MatMul_240","MatMul_238","MatMul_254","MatMul_302","MatMul_316","MatMul_326","MatMul_342","MatMul_340","MatMul_356","MatMul_404","MatMul_418","MatMul_428", "Add_118","Add_220","Add_322","Add_424","Mul_121","Mul_223","Mul_325","Mul_427", "Sub_24","Sub_102","Sub_126","Sub_204","Sub_228","Sub_306","Sub_330","Sub_408","Sub_432"]

pim_op_in_order = []
cpu_prof = os.path.join('cpu_1005.json')
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
            prof_data[node_name]['dma_size'] = int(int(item['args']['output_size']) / 4)
            incoming_nodes = item['args']['input_nodes'].split()
            outgoing_nodes = item['args']['output_nodes'].split() 
            prof_data[node_name]['src_nodes'] = incoming_nodes
            prof_data[node_name]['sink_nodes'] = outgoing_nodes
            prof_data[node_name]['in_edges'] = {}
            prof_data[node_name]['out_edges'] = {}
            NUM_OF_NODES += 1
            if node_name in pim_op_list:
                pim_op_in_order.append(node_name)

# print(prof_data['MatMul_34']['graph_index'])
# print(prof_data['Add_35']['graph_index'])

empty_datafield = Datafield(sink_ptr=None, size=None, sink_next_ptr=None, src_ptr=None, src_next_ptr=None)
node_list = list(prof_data.keys())

DCG = {}
# DCG['START'] = [None] * NUM_OF_DEVICES
# DCG['START'][0] = Datafield(None, None, None, None, None)

dev_list = ["cpu", "pimarm"]
for node_name in prof_data.keys():
    DCG[node_name] = [None] * NUM_OF_DEVICES
    for k in range(NUM_OF_DEVICES):
        DCG[node_name][k] = Datafield(None, None, None, None, None)

# DCG['END'] = [None] * NUM_OF_DEVICES
# DCG['END'][0] = Datafield(None, None, None, None, None)

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
                DCG[cur_node][dev_idx].size = attr['dma_size']

            if pim_src_nodes:
                if (pim_src_nodes[0], 1) not in source_list:
                    DCG[cur_node][dev_idx].src_ptr = (pim_src_nodes[0], 1)
                    source_list.append((pim_src_nodes[0], 1))
                if len(pim_src_nodes) > 1:
                    DCG[cur_node][dev_idx].src_next_ptr = []
                    for i in range(1, len(pim_src_nodes)):
                        src_data_field = Datafield(None, None, None, None, None)
                        if (pim_src_nodes[i], 1) not in source_list:
                            source_list.append((pim_src_nodes[i], 1))
                            src_data_field.src_ptr = (pim_src_nodes[i], 1)
                            DCG[cur_node][dev_idx].src_next_ptr.append(src_data_field)                            
        # 2. PIM device
        else:
            if cur_node not in pim_op_list:
                continue
            else:
                if sink_nodes:
                    DCG[cur_node][dev_idx].sink_ptr = (sink_nodes[0], 0)
                    DCG[cur_node][dev_idx].size = attr['dma_size']              
                if src_nodes:
                    if (src_nodes[0], 0) not in source_list:
                        source_list.append((src_nodes[0], 0))
                        DCG[cur_node][dev_idx].src_ptr = (src_nodes[0], 0)
                    if len(src_nodes) > 1:
                        DCG[cur_node][dev_idx].src_next_ptr = []
                        for i in range(1, len(src_nodes)):
                            src_data_field = Datafield(None, None, None, None, None)
                            if (src_nodes[i], 0) not in source_list:
                                source_list.append((src_nodes[i], 0))
                                src_data_field.src_ptr = (src_nodes[i], 0)
                                DCG[cur_node][dev_idx].src_next_ptr.append(src_data_field)  

# for k in range(NUM_OF_DEVICES):
#     first_dcg_node = DCG[node_list[0]][k]
#     if node_list[0] in pim_op_list or k == 0:
#         first_dcg_node.src_ptr = ('START', 0)
#         DCG['START'][0].sink_ptr = (node_list[0], k)
#     last_dcg_node = DCG[node_list[-1]][k]
#     if node_list[-1] in pim_op_list or k == 0:
#         last_dcg_node.sink_ptr = ('END', 0)
#         DCG['END'][0].src_ptr = (node_list[-1], k)    

# ## Check shape
# for key, data in DCG.items():
#     print(key, data)  

cut_vertex_candidate = [empty_datafield] * NUM_OF_DEVICES
dcg_node_list = list(DCG.keys())

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

def bin_path(n, path_len):
    if NUM_OF_DEVICES == 2:
        return format(n, f'0{path_len}b')
    else:
        if n == 0:
            return '0'*path_len
        nums = []
        while n:
            n, r = divmod(n, NUM_OF_DEVICES)
            nums.append(str(r))
        result = ''.join(reversed(nums))
        if len(result) < path_len:
            result = '0'*(path_len-len(result)) + result
        return result        

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

def updateMaxIdx(dnn_idx, dev_idx, max_idx):
    dnn_node = dcg_node_list[dnn_idx]
    if DCG[dnn_node][dev_idx].sink_next_ptr:
        last_sink_node, last_sink_dev = DCG[neighbor.dnn_idx][neighbor.dev_idx].sink_next_ptr[-1].sink_ptr
        if node_list.index(last_sink_node) > max_idx:
            max_idx = node_list.index(last_sink_node)
    return max_idx

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
   
num = 0
path_len = 1
idx = 0
max_idx = 0
# print(len(dcg_node_list))
current_edge_dict = {}
distinctEdgeSet = set()
pathTableQueue = {}
pathTableCnt = 0
max_entry_size = 0
max_path_len = 0
start = timeit.timeit()
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
                # print("max_num, num: ", max_num, num)
                currentPath = get_path(num, path_len, NUM_OF_DEVICES)
                # print(currentPath)
                currentNum = num
                num += 1
                nextPath = get_path(num, path_len, NUM_OF_DEVICES)
                # print("\ncurrentPath: ", currentPath)
                # print("nextPath: ", nextPath)
                backTrackIdx = currentNum ^ num
                # print("backtrack: ", get_path(backTrackIdx, path_len, NUM_OF_DEVICES))
                exclude_indices = get_path(currentNum & backTrackIdx, path_len, NUM_OF_DEVICES)
                include_indices = get_path(num & backTrackIdx, path_len, NUM_OF_DEVICES)
                changed_indices = get_path(backTrackIdx, path_len, NUM_OF_DEVICES)
                # print("exclude_indices: ", exclude_indices)
                for i in range(len(exclude_indices)):
                    dnn_idx = idx - path_len + 1 + i
                    if changed_indices[i] == '1':
                        # print(currentPath[i])
                        dev_idx = int(currentPath[i])
                        remove_edge(dnn_idx, dev_idx)
                # print("include_indices: ", include_indices)
                for i in range(len(include_indices)):
                    dnn_idx = idx - path_len + 1 + i
                    if changed_indices[i] == '1':
                        # print(nextPath[i])
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
end = timeit.timeit()
print("Length: ")
print(len(pathTableQueue))
print("Elapsed: ", start - end)
print("M: ", max_path_len)
print("L: ", max_entry_size)
# trackDistinctEdgeSet = set()

path_len = len(pathTableQueue)
num = 0
trackDistinctEdgeSet = set()
path_info_dict = {}
max_num = pow(max_entry_size, path_len)
while num != max_num:
    currentPath = get_path(num, path_len, max_entry_size)
    path_info_dict[num] = []
    for i in range(len(currentPath)):
        entry_idx = int(currentPath[i])
        edge_set_tuple = list(pathTableQueue[str(i)].keys())[entry_idx]
        edge_set = set(edge_set_tuple)
        path_info = pathTableQueue[str(i)][edge_set_tuple]
        path_info_dict[num].append(path_info)
        trackDistinctEdgeSet.update(edge_set)
    if distinctEdgeSet == trackDistinctEdgeSet:
        break
    num += 1

def update_path_table_2(idx, path_len, path_info, current_edge_set, finalPathTable):
    register_current_edge_set = False
    if not finalPathTable:
        # print("EMPTY")
        finalPathTable[tuple(current_edge_set)] = [path_info]
        print(finalPathTable)
    else:
        for edge_set_tuple in list(finalPathTable.keys()):
            edge_set = set(edge_set_tuple)
            print("edge_set: ", edge_set)
            if current_edge_set.issubset(edge_set):
                print("Is subset, break")
                register_current_edge_set = False
                break
            else:
                if current_edge_set.issuperset(edge_set):
                    del finalPathTable[edge_set_tuple]
                register_current_edge_set = True
    if register_current_edge_set:
        print("Register ", current_edge_set)
        finalPathTable[tuple(current_edge_set)] = []
        finalPathTable[tuple(current_edge_set)].append(path_info)   
    return finalPathTable

# path_len = len(pathTableQueue)
# num = 0
# trackDistinctEdgeSet = set()
# path_info_dict = {}
# finalPathTable = {}
# max_num = pow(max_entry_size, path_len) - 1
# currentEdgeSet = {}
# # Register
# currentPath = get_path(num, path_len, max_entry_size)
# for i in range(len(currentPath)):
#     print("i: ", i)
#     entry_idx = int(currentPath[i])
#     edge_set_tuple = list(pathTableQueue[str(i)].keys())[entry_idx]
#     edge_set = set(edge_set_tuple)
#     path_info = pathTableQueue[str(i)][edge_set_tuple]
#     current_edge_set.update(edge_set)
#     # path_info_dict[num].append(path_info)
#     finalPathTable = update_path_table_2(num, path_len, path_info, current_edge_set, finalPathTable)
# while num != max_num:
#     print("num: ", num)
#     currentPath = get_path(num, path_len, max_entry_size)
#     currentNum = num
#     num += 1
#     nextPath = get_path(num, path_len, max_entry_size)
#     backTrackIdx = currentNum ^ num
#     changed_indices = get_path(backTrackIdx, path_len, max_entry_size)

# print("HI?")
# print(finalPathTable)


print(path_info_dict)
minimumPathList = []
for num, path_info in path_info_dict.items():
    prev_idx = 0
    path = ''
    for i in range(len(path_info)):
        idx, local_path = path_info[i]
        path = path + '0' * (idx - prev_idx) + local_path
        prev_idx = idx + len(local_path)
        if i == len(path_info) - 1:
            path = path + '0' * (NUM_OF_NODES - idx - len(local_path))
    minimumPathList.append(path)
print(minimumPathList)
print(len(minimumPathList[0]))
print(NUM_OF_NODES)
part = {'cpu': [], 'pimarm': []}
dnn_partition = {"CPUExecutionProvider": [], "PIMARMExecutionProvider": []}
for path in minimumPathList:
    for i in range(len(path)):
        graph_index = prof_data[node_list[i]]["graph_index"]
        if path[i] == '0':
            print(node_list[i], 'cpu')
            part['cpu'].append(i)
            dnn_partition["CPUExecutionProvider"].append(graph_index)
        else:
            print(node_list[i], 'pimarm')
            if node_list[i] not in pim_op_list:
                print("ERRRROR")
                break
            part['pimarm'].append(int(i))
            dnn_partition["PIMARMExecutionProvider"].append(graph_index)

print(part)
print(dnn_partition)

