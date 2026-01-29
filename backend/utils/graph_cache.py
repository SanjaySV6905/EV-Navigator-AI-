import osmnx as ox
from fastapi import HTTPException
import os
import networkx as nx 

class GraphManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GraphManager, cls).__new__(cls)
            cls._instance.graphs = {}
        return cls._instance

    def get_graph(self, city_name: str):
        # 1. Check Memory Cache (Fastest)
        if city_name in self.graphs:
            return self.graphs[city_name]
        
        # 2. Check Disk Cache (Fast)
        # Create a safe filename (e.g., "bangalore.graphml")
        filename = f"{city_name.lower().replace(' ', '_')}.graphml"
        
        if os.path.exists(filename):
            print(f"📂 Loading {city_name} from local file '{filename}'...")
            try:
                # Load directly from file
                G = ox.load_graphml(filename)
                
                # Re-add speeds/times if they weren't saved properly (optional safety check)
                if not nx.get_edge_attributes(G, 'speed_kph'):
                     print("⚠️ Re-calculating edge speeds...")
                     try:
                        G = ox.add_edge_speeds(G)
                        G = ox.add_edge_travel_times(G)
                     except Exception:
                        hwy_speeds = {'residential': 30, 'secondary': 50, 'tertiary': 40, 'primary': 60, 'trunk': 80, 'motorway': 100}
                        G = ox.add_edge_speeds(G, hwy_speeds=hwy_speeds)
                        G = ox.add_edge_travel_times(G)

                self.graphs[city_name] = G
                print(f"✅ Graph loaded from disk!")
                return G
            except Exception as e:
                print(f"⚠️ Corrupt cache file, re-downloading: {e}")

        # 3. Download from Internet (Slow - First Run Only)
        print(f"🗺️  Downloading road network for {city_name}...")
        try:
            # --- REVERTED TO FULL CITY ---
            # We removed the Indiranagar restriction. 
            # Note: This download might take 2-5 minutes depending on internet speed.
            query = f"{city_name}, India"
            
            G = ox.graph_from_place(query, network_type='drive')
            
            # --- ROBUST SPEED HANDLING ---
            hwy_speeds = {
                'residential': 30, 
                'secondary': 50, 
                'tertiary': 40, 
                'primary': 60, 
                'trunk': 80, 
                'motorway': 100,
                'unclassified': 30
            }
            
            try:
                G = ox.add_edge_speeds(G)
            except Exception as e:
                print(f"⚠️ Missing maxspeed data, using fallbacks: {e}")
                G = ox.add_edge_speeds(G, hwy_speeds=hwy_speeds)
                
            G = ox.add_edge_travel_times(G)
            
            # Save to disk for next time
            ox.save_graphml(G, filename)
            print(f"💾 Saved graph to '{filename}' for future runs.")
            
            self.graphs[city_name] = G
            print(f"✅ Graph loaded and cached.")
            return G
        except Exception as e:
            print(f"❌ Error loading graph: {e}")
            raise HTTPException(status_code=404, detail=f"Could not load graph. {str(e)}")

graph_manager = GraphManager()