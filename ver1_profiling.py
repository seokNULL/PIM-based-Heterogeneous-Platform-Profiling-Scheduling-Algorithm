import json
import os
from dataclasses import dataclass
from statistics import median
import time

cpu_profile_file = 'cpu__2021-02-23_01-47-25.json'
pim_profile_file = 'pim__2021-02-23_01-48-23.json'


@dataclass
class Datafield:
    sink_ptr: tuple
    size: int
    sink_next_ptr: []
    src_ptr: tuple
    src_next_ptr: []
    color : str
    ua_edges : []

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

# Ignore sink_next_ptr
empty_datafield = Datafield(sink_ptr=None, size=None, sink_next_ptr=None, src_ptr=None, src_next_ptr=None, color=None, ua_edges=None)
node_list = list(prof_data.keys())

DCG = {}
dev_list = ["cpu", "pim"]
for node_name in prof_data.keys():
    DCG[node_name] = [None] * NUM_OF_DEVICES
    for k in range(NUM_OF_DEVICES):
        if k == 0:
            DCG[node_name][k] = Datafield(None, None, None, None, None, 'white', [])
        else:
            DCG[node_name][k] = Datafield(None, None, None, None, None, None, [])

edge_dict = {}
source_list = []
for cur_node, attr in prof_data.items():
    # print("Current node: ", cur_node)
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
                edge = ((cur_node, dev_idx), (pim_sink_nodes[0], 1))
                edge_attr = (dev_idx, 1, attr['elem_size'])
                edge_dict[edge] = [edge_attr, 'white']
            if pim_src_nodes:
                if (pim_src_nodes[0], 1) not in source_list:
                    DCG[cur_node][dev_idx].src_ptr = (pim_src_nodes[0], 1)
                    edge = ((pim_src_nodes[0], 1), (cur_node, dev_idx))
                    edge_attr = (1, dev_idx, attr['elem_size'])
                    source_list.append((pim_src_nodes[0], 1))
                if len(pim_src_nodes) > 1:
                    DCG[cur_node][dev_idx].src_next_ptr = []
                    for i in range(1, len(pim_src_nodes)):
                        src_data_field = Datafield(None, None, None, None, None, 'white', None)
                        if (pim_src_nodes[i], 1) not in source_list:
                            source_list.append((pim_src_nodes[i], 1))
                            src_data_field.src_ptr = (pim_src_nodes[i], 1)
                            edge = ((pim_src_nodes[i], 1), (cur_node, dev_idx))
                            edge_attr = (1, dev_idx, attr['elem_size'])
                            DCG[cur_node][dev_idx].src_next_ptr.append(src_data_field)                            
        # 2. PIM device
        else:
            if cur_node not in pim_op_list:
                continue
            else:
                DCG[cur_node][dev_idx].color = 'white'
                if sink_nodes:
                    DCG[cur_node][dev_idx].sink_ptr = (sink_nodes[0], 0)
                    DCG[cur_node][dev_idx].size = attr['elem_size']
                    edge = ((cur_node, dev_idx), (sink_nodes[0], 0))
                    edge_attr = (dev_idx, 0, attr['elem_size'])
                    edge_dict[edge] = [edge_attr, 'white']                              
                if src_nodes:
                    if (src_nodes[0], 0) not in source_list:
                        source_list.append((src_nodes[0], 0))
                        edge = ((src_nodes[0], 0), (cur_node, dev_idx))
                        edge_attr = (0, dev_idx, attr['elem_size'])
                        DCG[cur_node][dev_idx].src_ptr = (src_nodes[0], 0)
                    if len(src_nodes) > 1:
                        DCG[cur_node][dev_idx].src_next_ptr = []
                        for i in range(1, len(src_nodes)):
                            src_data_field = Datafield(None, None, None, None, None, 'white', None)
                            if (src_nodes[i], 0) not in source_list:
                                source_list.append((src_nodes[i], 0))
                                src_data_field.src_ptr = (src_nodes[i], 0)
                                edge = ((src_nodes[i], 0), (cur_node, dev_idx))
                                edge_attr = (0, dev_idx, attr['elem_size'])
                                DCG[cur_node][dev_idx].src_next_ptr.append(src_data_field)  


dcg_node_list = list(DCG.keys())

# # CHECK DCG
# for key, value in DCG.items():
#     print("\n", key)
#     for val in value:
#         print(val)

ua_edge_list = []
for key, values in edge_dict.items():
    value = values[0]
    attr = str(value[2]) + str(value[0]) + str(value[1])
    if attr not in ua_edge_list:
        ua_edge_list.append(attr)

# print(ua_edge_list)

#############
#### DFS ver 2.
#############

start_dfs = time.time()

visit = list()
queue = list()

group_idx = 0
node_idx = 0
group_final_node_idx = 0


# ua_edges = [[] for x in range(len(ua_edge_list))]
# ua_edge_map = {}
# for ua_edge in ua_edge_list:
#     ua_edge_map[ua_edge] = []

start_nodes = DCG[dcg_node_list[node_idx]]
for dev_idx, node_attr in enumerate(start_nodes):
    if node_attr.color != None:
        queue.append((node_idx, dev_idx))

# sy_list = []

ua_edge_map = {}

while queue:
    node_idx, dev_idx = queue.pop(0)
    node_attr = DCG[dcg_node_list[node_idx]][dev_idx]
    if node_attr.color == None:
        continue
    else:
        # print("\nPopped node: ", dcg_node_list[node_idx], "\t", dev_idx)
        try:
            src_node_name, src_dev_idx = DCG[dcg_node_list[node_idx]][dev_idx].src_ptr
            src_node_idx = dcg_node_list.index(src_node_name)
            dma_size = DCG[dcg_node_list[src_node_idx]][src_dev_idx].size
            ua_edge = str(dma_size) + str(src_dev_idx) + str(dev_idx)
            ua_edge_map[(node_idx, dev_idx)] = ua_edge

        except TypeError:
            pass
        if (node_idx, dev_idx) not in visit:
            if node_attr.color != None:
                visit.append((node_idx, dev_idx))
                if node_idx < len(dcg_node_list) - 1:
                    next_node_idx = node_idx + 1
                    next_node_list = []
                    for next_dev_idx, next_node in enumerate(DCG[dcg_node_list[next_node_idx]]):
                        if next_node.color != None:
                            next_node_list.append((next_node_idx, next_dev_idx))
                    queue.extend(next_node_list)

# print("--------------------------------------------")

# for key, value in ua_edge_map.items():
#     print(key, "\t", value)

reversed_node_list = list(ua_edge_map.keys())[::-1]

for node_name in reversed(dcg_node_list):
    for dev_idx in range(NUM_OF_DEVICES):
        # print("\nNode: ", node_name, "\t", dev_idx)
        node_idx = dcg_node_list.index(node_name)

        ### GET PREV ###
        DCG[node_name][dev_idx].ua_edges = [0] * len(ua_edge_list)
        try:
            next_node_name = dcg_node_list[node_idx + 1]
            for next_dev_idx, next_node_attr in enumerate(DCG[next_node_name]):
                for i in range(len(ua_edge_list)):
                    DCG[node_name][dev_idx].ua_edges[i] += DCG[next_node_name][next_dev_idx].ua_edges[i]
        except:
            pass

        for edge in reversed_node_list:
            (dst_node_idx, dst_dev_idx) = edge
            if dst_node_idx == node_idx and dst_dev_idx == dev_idx:
                ua_edge = ua_edge_map[edge]
                # print(ua_edge_list.index(ua_edge))
                DCG[node_name][dev_idx].ua_edges[ua_edge_list.index(ua_edge)] += 1

        for i in range(len(ua_edge_list)):
            if DCG[node_name][dev_idx].ua_edges[i] != 0:
                DCG[node_name][dev_idx].ua_edges[i] = 1

        # print(DCG[node_name][dev_idx].ua_edges)


# # CHECK DCG
# print("CHECK DCG")
# for key, value in DCG.items():
#     print("\n", key)
#     for val in value:
#         print(val)

path = [None] * len(dcg_node_list)
movetolast = lambda l, e: [x for x in l if x != e] + [e]

visited = []
node_cnt_map = {}

for node_name, node_attrs in DCG.items():
    node_idx = dcg_node_list.index(node_name)
    next_node_idx = node_idx + 1
    max_cnt = 0
    try:
        for node_attr in DCG[dcg_node_list[next_node_idx]]:
            if node_attr.color != None:
                max_cnt += 1
    except IndexError:
        max_cnt = 0
    if node_name == dcg_node_list[-1]:
        node_cnt_map[node_idx] = {"max_cnt" : -1, "node_cnt" : -1, "adj_list" : [], "org_adj_list" : []}
    else:
        ## OPPOSITE
        # node_cnt_map[node_idx] = {"max_cnt" : max_cnt - 1, "node_cnt" : max_cnt - 1, "adj_list" : list(range(max_cnt)), "org_adj_list" : []}
        ## NAIVE
        node_cnt_map[node_idx] = {"max_cnt" : max_cnt - 1, "node_cnt" : max_cnt - 1, "adj_list" : list(range(max_cnt))[::-1], "org_adj_list" : []}
    node_cnt_map[node_idx]["org_adj_list"] = node_cnt_map[node_idx]["adj_list"][:]

# for key, value in node_cnt_map.items():
#     node_name = dcg_node_list[key]
#     print(node_name, "\t", value['adj_list'])

path_table = {}
ua_edges = [0 for x in range(len(ua_edge_list))]

node_cnt = 0

found_optimal = False

def findPaths(node_idx, dev_idx):
    global found_optimal
    print("\nCurrent node: ", dcg_node_list[node_idx], "\t", dev_idx)
    global node_cnt
    assert node_idx == node_cnt
    path[node_cnt] = dev_idx
    node_cnt += 1
    DCG[dcg_node_list[node_idx]][dev_idx].color = 'black'
    finished = True
    next_node_idx = node_idx + 1

    # ################# PATH PRINT #####################
    # print("--------- PATH ----------")
    # for i in range(0, node_cnt):
    #     print(dcg_node_list[i], "\t", path[i])
    # ##################################################

    try:
        src_node_name, src_dev_idx = DCG[dcg_node_list[node_idx]][dev_idx].src_ptr
        # print("src_node_name: ", src_node_name)
        src_node_idx = dcg_node_list.index(src_node_name)
        if path[src_node_idx] == src_dev_idx:
            dma_size = DCG[dcg_node_list[src_node_idx]][src_dev_idx].size
            ua_edge = str(dma_size) + str(src_dev_idx) + str(dev_idx)
            # print("ua_edge: ", ua_edge, "\t", ua_edge_list.index(ua_edge))
            ua_edges[ua_edge_list.index(ua_edge)] += 1
    except TypeError:
        pass

    while(node_cnt_map[node_idx]['adj_list']):
        next_dev_idx = node_cnt_map[node_idx]['adj_list'].pop()
        if DCG[dcg_node_list[next_node_idx]][next_dev_idx].color == "white":
            finished = False
            findPaths(next_node_idx, next_dev_idx)
    not_found_edge =[]
    if finished:
        print("REACHED THE END")
        new_path = ''.join(str(p) for p in path)
        if node_idx == len(dcg_node_list) - 1 and not found_optimal:
            # print("path_table: ", path_table)
            # ############################################
            # ######### OPTIMIZING PATH TABLE ############
            # ############################################
            # register_flag = False
            # new_edge_set = set([x_idx for x_idx, x in enumerate(ua_edges) if x == 1])
            # if not path_table:
            #     register_flag = True
            # path_keys = list(path_table.keys())
            # # print("new_edge_set: ", new_edge_set)
            # for path_key in path_keys:
            #     edge_set = set([x_idx for x_idx, x in enumerate(path_table[path_key]) if x == 1])
            #     # print("edge_set: ", edge_set)
            #     if new_edge_set.issubset(edge_set):
            #         register_flag = False
            #         break
            #     else:
            #         if new_edge_set.issuperset(edge_set):
            #             del path_table[path_key]
            #         register_flag = True
            # if register_flag:
            #     path_table[new_path] = ua_edges

            path_table[new_path] = ua_edges

        if 0 in ua_edges:
            not_found_edge = [x_idx for x_idx, x in enumerate(ua_edges) if x == 0]
            print(not_found_edge)
            print("NOT FOUND MUST EDGE. CONTINUE.")
        else:
            print("FOUND ALL DISTINCT EDGE")
            found_optimal = True

    if not found_optimal:
        DCG[dcg_node_list[node_idx]][dev_idx].color = 'white'
        if node_cnt_map[node_idx]["max_cnt"] != -1:
            node_cnt_map[node_idx]["adj_list"] = node_cnt_map[node_idx]["org_adj_list"][:]

    node_cnt -= 1

# Find path that contains. 
findPaths(0, 0)

end_dfs = time.time()

print("DFS time: ", end_dfs - start_dfs)

print(len(path_table))
# print(len(pim_op_list))