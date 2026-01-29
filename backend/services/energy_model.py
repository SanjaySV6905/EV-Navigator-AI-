import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor

class EnergyPredictor:
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.is_trained = False

    def train_mock_model(self):
        """
        Trains a model on synthetic physics-based data on startup.
        """
        if self.is_trained:
            return

        print("⚡ Training AI Energy Model...")
        np.random.seed(42)
        n_samples = 2000
        
        # Synthetic Features
        distance = np.random.uniform(0.5, 20, n_samples)
        speed = np.random.uniform(10, 60, n_samples)
        load = np.random.uniform(0, 500, n_samples)
        traffic = np.random.uniform(0, 10, n_samples)
        elevation = np.random.uniform(-50, 50, n_samples)
        temp = np.random.uniform(15, 40, n_samples)

        # Physics-based Consumption Formula (Target Variable)
        # 0.15 kWh/km base + factors
        energy_consumption = (
            (distance * 0.15) +           
            (load * 0.0005 * distance) +  
            (traffic * 0.01 * distance) + 
            (speed ** 2 * 0.0001) +       
            (abs(elevation) * 0.005) +    
            (abs(temp - 25) * 0.002)      
        )
        
        X = pd.DataFrame({
            'distance_km': distance, 'avg_speed': speed, 'vehicle_load_kg': load,
            'traffic_level': traffic, 'elevation_change': elevation, 'temperature': temp
        })
        
        self.model.fit(X, energy_consumption)
        self.is_trained = True
        print("✅ AI Model Trained.")

    def predict(self, distance_km: float) -> float:
        if not self.is_trained:
            self.train_mock_model()
            
        # For this demo, we assume average conditions for the user's specific trip
        # In a real app, you'd fetch real-time traffic/weather here
        features = {
            'distance_km': distance_km,
            'avg_speed': 30.0,
            'vehicle_load_kg': 100.0,
            'traffic_level': 5.0,
            'elevation_change': 0,
            'temperature': 30.0
        }
        
        df = pd.DataFrame([features])
        return float(self.model.predict(df)[0])

energy_predictor = EnergyPredictor()