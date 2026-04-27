/* ============================================================
   routing.js — handles route requests and map rendering
   ============================================================ */

var segmentLayers = [];

async function calculateRoute(viaStationsArray) {
    if (viaStationsArray === undefined) viaStationsArray = null;

    var sLat  = document.getElementById('startLat').value;
    var sLon  = document.getElementById('startLon').value;
    var eLat  = document.getElementById('endLat').value;
    var eLon  = document.getElementById('endLon').value;
    var cap   = parseFloat(document.getElementById('batteryCap').value);
    var level = parseFloat(document.getElementById('batteryLevel').value);
    var load  = parseFloat(document.getElementById('vehicleLoad').value) || 100.0;
    var speed = parseFloat(document.getElementById('selectedSpeed').value) || 70.0;
    var city  = document.getElementById('city').value;

    if (!sLat || !sLon || !eLat || !eLon) {
        alert('Please set Start and Destination points on the map.');
        return;
    }

    showSpinner();
    hideResults();
    clearRoute();
    clearRouteMarkers();

    var payload = {
        city: city,
        start_lat:            parseFloat(sLat),
        start_lon:            parseFloat(sLon),
        end_lat:              parseFloat(eLat),
        end_lon:              parseFloat(eLon),
        battery_capacity_kwh: cap,
        battery_level_pct:    level,
        vehicle_load_kg:      load,
        speed_kmh:            speed,
        stations:             allCityStations,
    };
    if (viaStationsArray && viaStationsArray.length > 0) {
        payload.via_stations = viaStationsArray;
    }

    try {
        var resp = await fetch(API_URL + '/route', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(payload),
        });
        if (!resp.ok) {
            var err = await resp.json();
            throw new Error(err.detail || 'Backend error');
        }
        var data = await resp.json();

        // ── Pick the active route (fastest wins) ──────────────────────────────
        var routeData = data;
        if (data.fastest_route && data.fastest_route.route_coords) {
            routeData = Object.assign({}, data.fastest_route, {
                opt_a_home_charge_plan:    data.opt_a_home_charge_plan   || data.fastest_route.opt_a_home_charge_plan,
                opt_b_nearest_station_plan: data.opt_b_nearest_station_plan || data.fastest_route.opt_b_nearest_station_plan,
                alternative_stations:      data.alternative_stations      || data.fastest_route.alternative_stations,
            });
        } else if (data.shortest_route && data.shortest_route.route_coords) {
            routeData = Object.assign({}, data.shortest_route, {
                opt_a_home_charge_plan:    data.opt_a_home_charge_plan   || data.shortest_route.opt_a_home_charge_plan,
                opt_b_nearest_station_plan: data.opt_b_nearest_station_plan || data.shortest_route.opt_b_nearest_station_plan,
                alternative_stations:      data.alternative_stations      || data.shortest_route.alternative_stations,
            });
        }

        // ── Draw the base route (always shortest/direct) ─────────────────────
        var baseCoords = (data.shortest_route && data.shortest_route.route_coords)
            ? data.shortest_route.route_coords
            : routeData.route_coords;
        drawRoute(baseCoords);

        // ── Update sidebar summary ────────────────────────────────────────────
        updateSummary(routeData.distance_km, routeData.energy_consumption_kwh, routeData);

        // ── Render numbered charging stop markers on map ──────────────────────
        var planA = routeData.opt_a_home_charge_plan;
        var planB = routeData.opt_b_nearest_station_plan;

        if (routeData.charging_stops && routeData.charging_stops.length > 0) {
            // Direct route has stops — show them numbered
            renderChargingStops(routeData.charging_stops);

            // Also register plan toggle for map switching
            window.renderActivePlanStations = function (type) {
                var plan = type === 'home' ? planA : planB;
                if (plan && plan.hops && plan.hops.length > 0) {
                    renderHopsAsStopMarkers(plan.hops);
                } else {
                    renderChargingStops(routeData.charging_stops);
                }
            };

        } else if (routeData.charging_needed) {
            // No direct stops found — show markers from Plan A by default
            var defaultPlan = planA || planB;
            if (defaultPlan && defaultPlan.hops && defaultPlan.hops.length > 0) {
                renderHopsAsStopMarkers(defaultPlan.hops);
            }

            window.renderActivePlanStations = function (type) {
                var plan = type === 'home' ? planA : planB;
                if (plan && plan.hops && plan.hops.length > 0) {
                    renderHopsAsStopMarkers(plan.hops);
                }
            };
        }

        // ── Render all other stations as small map icons ──────────────────────
        renderAlternativeStations(routeData.alternative_stations || [], routeData.charging_stops || []);

    } catch (error) {
        alert('Error: ' + error.message + '\nMake sure the Python backend is running!');
        console.error(error);
    } finally {
        hideSpinner();
        nextClickType = 'start';
        document.getElementById('mapHint').innerHTML = 'Click map to set Start point';
    }
}

// ── Reroute helpers ───────────────────────────────────────────────────────────

function rerouteViaStations(stationsArray) {
    calculateRoute(stationsArray);
}

function rerouteViaStation(lat, lon) {
    calculateRoute([{ lat: lat, lon: lon }]);
}

// ── Map helpers ───────────────────────────────────────────────────────────────

function clearRouteMarkers() {
    ['markers', 'segmentLayers', 'altMarkers', 'stationMarkers'].forEach(function (name) {
        if (typeof window[name] !== 'undefined' && window[name]) {
            window[name].forEach(function (m) { map.removeLayer(m); });
            window[name] = [];
        }
    });
}

function clearAllMarkers() {
    clearRouteMarkers();
    if (typeof cityStationMarkers !== 'undefined') {
        cityStationMarkers.forEach(function (m) { map.removeLayer(m); });
        cityStationMarkers = [];
    }
}

function drawRoute(coords) {
    if (typeof routeLayer !== 'undefined' && routeLayer) map.removeLayer(routeLayer);
    routeLayer = L.polyline(coords, { color: '#2563eb', weight: 5, opacity: 0.75 }).addTo(map);
    map.fitBounds(routeLayer.getBounds(), { padding: [40, 40] });
    addMarker(coords[0],                 'Start');
    addMarker(coords[coords.length - 1], 'Destination');
}
