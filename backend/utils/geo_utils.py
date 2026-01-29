import networkx as nx

def extract_route_coords(G, route_nodes):
    """
    Converts a list of NetworkX node IDs into a list of (lat, lon) tuples.
    """
    route_coords = []
    for node in route_nodes:
        point = G.nodes[node]
        route_coords.append((point['y'], point['x']))
    return route_coords

def calculate_path_length(G, route_nodes):
    """
    Calculates total distance of the path in Kilometers.
    """
    distance_m = nx.path_weight(G, route_nodes, weight='length')
    return distance_m / 1000.0