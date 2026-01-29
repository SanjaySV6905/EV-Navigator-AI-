// --- CONFIGURATION ---
const API_URL = "http://localhost:8000"; 
const cityCoords = {
    "Bangalore": {lat: 12.9716, lon: 77.5946},
    "Chennai": {lat: 13.0827, lon: 80.2707}
};

// --- APP INITIALIZATION ---
document.addEventListener("DOMContentLoaded", () => {
    // 1. Initialize Map with default city
    const defaultCity = "Bangalore";
    initMap(cityCoords[defaultCity].lat, cityCoords[defaultCity].lon);

    // 2. Setup Event Listeners
    document.getElementById('city').addEventListener('change', handleCityChange);
    document.getElementById('getRouteBtn').addEventListener('click', calculateRoute);

    // 3. Setup Autocomplete
    setupAutocomplete();

    // 4. Initial Station Load
    fetchStationsForCity(defaultCity);
});

// Handle City Switching
async function handleCityChange() {
    const city = document.getElementById('city').value;
    const coords = cityCoords[city];
    
    // Update Map View (map.js)
    updateMapView(coords.lat, coords.lon);
    
    // Clear Map Data (map.js)
    clearMarkers();
    clearRoute();

    // Fetch New Stations (stations.js)
    await fetchStationsForCity(city);
}