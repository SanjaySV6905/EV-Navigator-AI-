async function calculateRoute() {
    const sLat = document.getElementById('startLat').value;
    const sLon = document.getElementById('startLon').value;
    const eLat = document.getElementById('endLat').value;
    const eLon = document.getElementById('endLon').value;
    const cap = parseFloat(document.getElementById('batteryCap').value);
    const city = document.getElementById('city').value;

    if (!sLat || !sLon || !eLat || !eLon) { 
        alert("Please set Start and Destination points."); 
        return; 
    }

    showSpinner();
    hideResults();
    clearRoute();
    
    // Clear manual click markers to replace with route endpoints
    clearMarkers(); 

    try {
        // CALL PYTHON BACKEND
        const response = await fetch(`${API_URL}/route`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                city, 
                start_lat: parseFloat(sLat), 
                start_lon: parseFloat(sLon), 
                end_lat: parseFloat(eLat), 
                end_lon: parseFloat(eLon), 
                battery_capacity_kwh: cap
            })
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Backend Error");
        }
        
        const data = await response.json();
        
        // 1. Draw Route
        drawRoute(data.route_coords);
        
        // 2. Update UI Stats
        updateSummary(data.distance_km, data.energy_consumption_kwh);
        
        // 3. Filter Stations based on logic
        filterStationsByRoute(data.route_coords, data.distance_km, data.energy_consumption_kwh);

    } catch (error) {
        alert("Error: " + error.message + "\nEnsure Python backend is running!");
        console.error(error);
    } finally {
        hideSpinner();
        nextClickType = 'start';
        document.getElementById('mapHint').innerHTML = "📍 Click map to set <b>Start</b> point";
    }
}

function drawRoute(coords) {
    if (routeLayer) map.removeLayer(routeLayer);
    
    routeLayer = L.polyline(coords, { 
        color: 'blue', 
        weight: 5, 
        opacity: 0.7 
    }).addTo(map);
    
    map.fitBounds(routeLayer.getBounds());
    
    addMarker(coords[0], "Start");
    addMarker(coords[coords.length-1], "Destination");
}