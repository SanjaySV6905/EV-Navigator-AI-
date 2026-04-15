let stationMarkers  = [];
let allCityStations = [];
let altMarkers      = [];

function renderChargingStops(stops) {
    stationMarkers.forEach(m => map.removeLayer(m));
    stationMarkers = [];
    if (!stops || stops.length === 0) { updateBadge("No charging stops needed", "bg-green-100 text-green-800"); return; }

    stops.forEach((s, idx) => {
        const color = s.will_run_out ? "#dc2626" : "#d97706";
        const icon = L.divIcon({
            className: "",
            html: "<div style=\"background:" + color + ";color:#fff;border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:14px;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.4);cursor:pointer;\">" + (idx+1) + "</div>",
            iconSize: [32,32], iconAnchor: [16,32], popupAnchor: [0,-34]
        });
        const m = L.marker([s.lat, s.lon], { icon, zIndexOffset: 1000 }).addTo(map);
        const warn = s.will_run_out
            ? "<p style=\"color:#dc2626;font-weight:bold\">Battery will hit 0% before here!<br>Charge to at least <b>" + s.charge_to_pct + "%</b> before leaving (10% buffer)</p>"
            : "";
        const journeyInfo = s._arrDest !== undefined
            ? "<hr style=\"margin:6px 0\"><p style=\"font-size:11px;color:#374151\"><b>Journey Plan:</b></p><p style=\"font-size:11px\">Home: charge to <b>" + (s.charge_to_pct || "?") + "%</b></p><p style=\"font-size:11px\">Arrive here ~10% then charge to 80%</p><p style=\"font-size:11px\">Reach dest with ~<b>" + s._arrDest + "%</b></p>"
            : "";
        m.bindPopup("<b style=\"color:" + color + "\"> " + s.label + "</b><br><b>" + s.name + "</b><br>Arrive: <b>" + s.arrive_pct + "%</b><br>Charge to: <b>" + s.depart_pct + "%</b><br>Segment: <b>" + s.segment_km + " km</b><br>" + warn + journeyInfo + "<button onclick=\"rerouteViaStation(" + s.lat + "," + s.lon + ")\" style=\"margin-top:6px;background:#2563eb;color:#fff;border:none;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:12px;\">Reroute via this station</button>");
        setTimeout(() => m.openPopup(), 600 * (idx + 1));
        stationMarkers.push(m);
    });
    updateBadge(stops.length + " charging stop(s) planned", "bg-orange-100 text-orange-800");
}

function renderAlternativeStations(altStations, recommendedStops) {
    altMarkers.forEach(m => map.removeLayer(m));
    altMarkers = [];
    if (!altStations || altStations.length === 0) return;
    const recSet = new Set((recommendedStops || []).map(s => s.lat + "," + s.lon));
    altStations.forEach(s => {
        if (recSet.has(s.lat + "," + s.lon)) return;
        const icon = L.icon({ iconUrl: "images/icon.jpg", iconSize: [30,30], iconAnchor: [15,30], popupAnchor: [0,-32], className: s.reachable ? "" : "grayscale-icon" });
        const m = L.marker([s.lat, s.lon], { icon, zIndexOffset: 500 }).addTo(map);
        const btn = s.reachable
            ? "<p style=\"color:#16a34a;font-size:11px;margin-bottom:4px;\">Reachable - optional top-up</p><button onclick=\"rerouteViaStation(" + s.lat + "," + s.lon + ")\" style=\"background:#2563eb;color:#fff;border:none;padding:3px 8px;border-radius:4px;cursor:pointer;font-size:11px;\">Reroute via this station</button>"
            : "<p style=\"color:#dc2626;font-size:11px;margin-top:4px;\">Battery will reach 0% before here</p>";
        m.bindPopup("<b>" + (s.reachable ? "Reachable Station" : "Out of Range") + "</b><br><b>" + s.name + "</b><br>Arrive: <b>" + s.arrive_pct + "%</b><br>Distance: <b>" + s.segment_km + " km</b><br>" + btn);
        altMarkers.push(m);
    });
}

async function fetchStationsForCity(city) {
    updateBadge("Finding Chargers in " + city + "...", "bg-yellow-100 text-yellow-800");
    const coords = cityCoords[city];
    const lat = coords ? coords.lat : 12.9716;
    const lon = coords ? coords.lon : 77.5946;
    try {
        const controller = new AbortController();
        const tid = setTimeout(() => controller.abort(), 35000);
        const res = await fetch(API_URL + "/charging-stations?city=" + city, { signal: controller.signal });
        clearTimeout(tid);
        if (!res.ok) throw new Error("error");
        const raw = await res.json();
        if (!raw || raw.length === 0) throw new Error("empty");
        allCityStations = raw;
        renderStations(allCityStations);
        return;
    } catch (e) { console.warn("Backend stations failed, trying Overpass...", e.message); }
    try {
        const q = "[out:json][timeout:30];(node[\"amenity\"=\"charging_station\"](around:30000," + lat + "," + lon + ");way[\"amenity\"=\"charging_station\"](around:30000," + lat + "," + lon + "););out center;";
        const res  = await fetch("https://overpass-api.de/api/interpreter?data=" + encodeURIComponent(q));
        const data = await res.json();
        allCityStations = [];
        (data.elements || []).forEach(el => {
            const slat = el.lat || (el.center && el.center.lat);
            const slon = el.lon  || (el.center && el.center.lon);
            if (slat && slon) allCityStations.push({ lat: slat, lon: slon, name: (el.tags && el.tags.name) || "Public Charger" });
        });
        if (allCityStations.length > 0) renderStations(allCityStations);
        else updateBadge("No stations found", "bg-gray-100 text-gray-800");
    } catch (e) {
        console.error("Overpass failed:", e);
        updateBadge("Could not load stations", "bg-red-100 text-red-800");
    }
}

function renderStations(stations) {
    stationMarkers.forEach(m => map.removeLayer(m));
    stationMarkers = [];
    if (!stations || stations.length === 0) { updateBadge("No Chargers Found", "bg-gray-100 text-gray-800"); return; }
    const icon = L.icon({ iconUrl: "images/icon.jpg", iconSize: [36,36], iconAnchor: [18,36], popupAnchor: [0,-36] });
    stations.forEach(s => {
        const m = L.marker([s.lat, s.lon], { icon }).addTo(map);
        m.bindPopup("<b>" + s.name + "</b><br>EV Charging Station");
        stationMarkers.push(m);
    });
    updateBadge(stations.length + " stations in city", "bg-green-100 text-green-800");
}
