let stationMarkers = [];
let allCityStations = [];

// Icons
// NOTE: Make sure 'icon.jpg' is inside the 'frontend' folder, next to index.html
const iconGreen = L.icon({
    iconUrl: './icon.jpg', 
    iconSize: [40, 40], // Size of the icon in pixels
    iconAnchor: [20, 40], // Point of the icon which will correspond to marker's location
    popupAnchor: [0, -40] // Point from which the popup should open relative to the iconAnchor
    // Removed 'className' to ensure the image displays exactly as saved
});

const iconOrange = L.icon({
    iconUrl: './icon.jpg', 
    iconSize: [50, 50], // Slightly larger for recommended
    iconAnchor: [25, 50], 
    popupAnchor: [0, -50]
    // Removed 'className'
});

// Fetch Logic
async function fetchStationsForCity(city, lat, lon) {
    updateBadge(`🔍 Finding Chargers in ${city}...`, "bg-yellow-100 text-yellow-800");

    try {
        // Try Backend First
        const response = await fetch(`${API_URL}/charging-stations?city=${city}`);
        if (!response.ok) throw new Error("Backend Offline");
        allCityStations = await response.json();
        allCityStations = allCityStations.map(s => ({...s, source: "Backend Data"}));
        renderStations(allCityStations, "City View");

    } catch (error) {
        console.warn("Backend offline. Using Overpass API.");
        // Fallback to Overpass API (Real Data)
        const query = `
            [out:json][timeout:25];
            (
              node["amenity"="charging_station"](around:30000,${lat},${lon});
              way["amenity"="charging_station"](around:30000,${lat},${lon});
            );
            out center;
        `;
        try {
            const url = `https://overpass-api.de/api/interpreter?data=${encodeURIComponent(query)}`;
            const res = await fetch(url);
            const data = await res.json();
            
            // Clear previous data before refilling
            allCityStations = []; 
            if (data.elements) {
                data.elements.forEach(el => {
                    const slat = el.lat || el.center.lat;
                    const slon = el.lon || el.center.lon;
                    allCityStations.push({
                        lat: slat, lon: slon, 
                        name: el.tags.name || "Public Charger",
                        source: "Real Data (Overpass)"
                    });
                });
            }
            renderStations(allCityStations, "City View");
        } catch (e) {
            updateBadge("❌ Could not load stations", "bg-red-100 text-red-800");
        }
    }
}

// Render Logic
function renderStations(stationsToRender, viewMode, recommendedStation = null) {
    stationMarkers.forEach(m => map.removeLayer(m));
    stationMarkers = [];

    if (stationsToRender.length === 0) {
        updateBadge("No Chargers Found", "bg-gray-100 text-gray-800");
        return;
    }

    stationsToRender.forEach(s => {
        // Check if this station matches the recommended one (using small tolerance for floats)
        const isRecommended = recommendedStation && 
                              Math.abs(s.lat - recommendedStation.lat) < 0.0001 && 
                              Math.abs(s.lon - recommendedStation.lon) < 0.0001;
        
        const marker = L.marker([s.lat, s.lon], {
            icon: isRecommended ? iconOrange : iconGreen,
            zIndexOffset: isRecommended ? 1000 : 0
        }).addTo(map);

        let popupContent = `<b>${s.name}</b><br>EV Charging Station`;
        if (isRecommended) {
            popupContent = `<b style="color: #d97706">⭐ RECOMMENDED STOP</b><br>` + popupContent;
            // Auto open popup for recommended station
            setTimeout(() => marker.openPopup(), 500);
        }

        marker.bindPopup(popupContent);
        stationMarkers.push(marker);
    });

    if (viewMode === "Route View") {
        updateBadge(`✅ Found ${stationsToRender.length} chargers near route`, "bg-blue-100 text-blue-800");
    } else {
        updateBadge(`📍 Showing all ${stationsToRender.length} stations in city`, "bg-green-100 text-green-800");
    }
}

// --- NEW: Find Nearest Station Logic ---
function findNearestStation() {
    const sLat = parseFloat(document.getElementById('startLat').value);
    const sLon = parseFloat(document.getElementById('startLon').value);

    if (!sLat || !sLon) {
        alert("Please set a Start Location first (Click map or search).");
        return;
    }

    if (allCityStations.length === 0) {
        alert("No charging stations loaded for this city.");
        return;
    }

    let nearest = null;
    let minDistance = Infinity;

    allCityStations.forEach(s => {
        const dist = getDistanceFromLatLonInM(sLat, sLon, s.lat, s.lon);
        if (dist < minDistance) {
            minDistance = dist;
            nearest = s;
        }
    });

    if (nearest) {
        // Highlight the nearest station
        renderStations(allCityStations, "City View", nearest);
        
        // Zoom to fit start point and nearest station
        const group = new L.featureGroup([
            L.marker([sLat, sLon]),
            L.marker([nearest.lat, nearest.lon])
        ]);
        map.fitBounds(group.getBounds().pad(0.2));
        
        alert(`Nearest Station: ${nearest.name} is ${(minDistance/1000).toFixed(2)} km away.`);
    }
}

// --- IMPROVED RECOMMENDATION LOGIC ---
function filterStationsByRoute(routeCoords, totalDistKm, predictedEnergy) {
    if (!allCityStations.length || !routeCoords.length) return;

    const cap = parseFloat(document.getElementById('batteryCap').value);
    const level = parseFloat(document.getElementById('batteryLevel').value);
    const currentEnergy = cap * (level / 100);
    
    // Logic: Recommend charge if we finish with less than 20% battery
    const remainingEnergy = currentEnergy - predictedEnergy;
    const remainingPercent = (remainingEnergy / cap) * 100;
    const chargingNeeded = remainingPercent < 20; 

    // Filter stations near route (500m buffer)
    const THRESHOLD_METERS = 500;
    const nearStations = allCityStations.filter(station => {
        // Optimization: Check every 10th point
        for (let i = 0; i < routeCoords.length; i += 10) {
            const routePt = routeCoords[i];
            if (getDistanceFromLatLonInM(station.lat, station.lon, routePt[0], routePt[1]) <= THRESHOLD_METERS) {
                return true;
            }
        }
        return false;
    });

    let recommended = null;

    if (chargingNeeded && nearStations.length > 0) {
        // Find the "Point of No Return" or a safe stopping point (20% buffer)
        const kmPerKwh = totalDistKm / predictedEnergy;
        // Distance we can travel before hitting 20% battery
        const safeRangeKm = (currentEnergy - (cap * 0.2)) * kmPerKwh; 
        
        let ratio = safeRangeKm / totalDistKm;
        
        // Clamp ratio to ensure reasonable suggestions
        if (ratio > 0.8) ratio = 0.5; // If we almost make it, suggest midpoint
        if (ratio < 0.1) ratio = 0.1; // Don't suggest immediately at start

        // Find the coordinate on the route that matches this ratio
        const targetIndex = Math.floor(routeCoords.length * ratio);
        const targetPoint = routeCoords[targetIndex];

        // Find station closest to this optimal target point
        let minDist = Infinity;
        nearStations.forEach(s => {
            const d = getDistanceFromLatLonInM(s.lat, s.lon, targetPoint[0], targetPoint[1]);
            if (d < minDist) {
                minDist = d;
                recommended = s;
            }
        });
        
        console.log("Recommended Station:", recommended);
    }

    renderStations(nearStations, "Route View", recommended);
}

// Helper: Haversine Distance
function getDistanceFromLatLonInM(lat1, lon1, lat2, lon2) {
    var R = 6371; 
    var dLat = (lat2-lat1) * (Math.PI/180); 
    var dLon = (lon2-lon1) * (Math.PI/180); 
    var a = Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(lat1 * (Math.PI/180)) * Math.cos(lat2 * (Math.PI/180)) * Math.sin(dLon/2) * Math.sin(dLon/2); 
    var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)); 
    return R * c * 1000;
}