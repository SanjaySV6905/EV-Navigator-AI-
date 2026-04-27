let map;
let markers = [];
let routeLayer = null;
let nextClickType = 'start';

function initMap(lat, lon) {
    map = L.map('map').setView([lat, lon], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    map.on('click', handleMapClick);
}

async function handleMapClick(e) {
    const { lat, lng } = e.latlng;
    const hintBox = document.getElementById('mapHint');

    if (nextClickType === 'start') {
        clearMarkers();
        clearRoute();
        if (typeof allCityStations !== 'undefined' && allCityStations.length) {
            renderStations(allCityStations);
        }
        document.getElementById('startLat').value = lat.toFixed(6);
        document.getElementById('startLon').value = lng.toFixed(6);
        document.getElementById('startAddr').value = "Fetching address...";
        addMarker([lat, lng], "Start Location");
        reverseGeocode(lat, lng, 'start');
        nextClickType = 'end';
        hintBox.innerHTML = "📍 Now click map to set <b>Destination</b>";
    } else {
        document.getElementById('endLat').value = lat.toFixed(6);
        document.getElementById('endLon').value = lng.toFixed(6);
        document.getElementById('endAddr').value = "Fetching address...";
        addMarker([lat, lng], "Destination");
        reverseGeocode(lat, lng, 'end');
        nextClickType = 'start';
        hintBox.innerHTML = "🚀 Click 'Get Optimized Route' or click map to reset";
    }
}

function addMarker(coords, title) {
    const m = L.marker(coords).addTo(map).bindPopup(title).openPopup();
    markers.push(m);
}

function clearMarkers() {
    markers.forEach(m => map.removeLayer(m));
    markers = [];
}

function clearRoute() {
    if (routeLayer) { map.removeLayer(routeLayer); routeLayer = null; }
}

function updateMapView(lat, lon) {
    if (map) map.setView([lat, lon], 12);
}

async function reverseGeocode(lat, lon, type) {
    try {
        const res  = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&accept-language=en`);
        const data = await res.json();
        document.getElementById(`${type}Addr`).value = data.display_name || `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
    } catch(e) {
        document.getElementById(`${type}Addr`).value = "Address not found";
    }
}
