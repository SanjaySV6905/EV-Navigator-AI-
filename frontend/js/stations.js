/* ============================================================
   stations.js — map markers for charging stops and city stations
   ============================================================ */

var stationMarkers     = [];
var cityStationMarkers = [];
var allCityStations    = [];
var altMarkers         = [];

// ── Numbered orange stop markers (from direct route stops) ────────────────────

function renderChargingStops(stops) {
    stationMarkers.forEach(function (m) { map.removeLayer(m); });
    stationMarkers = [];

    if (!stops || stops.length === 0) {
        updateBadge('No charging stops needed', 'bg-green-100 text-green-800');
        return;
    }

    stops.forEach(function (s, idx) {
        _addStopMarker(s.lat, s.lon, idx + 1, s, false);
    });

    updateBadge(stops.length + ' charging stop(s) planned', 'bg-orange-100 text-orange-800');
}

// ── Numbered markers from plan A or B hop arrays ──────────────────────────────

function renderHopsAsStopMarkers(hops) {
    stationMarkers.forEach(function (m) { map.removeLayer(m); });
    stationMarkers = [];

    if (!hops || hops.length === 0) {
        updateBadge('No charging stops needed', 'bg-green-100 text-green-800');
        return;
    }

    hops.forEach(function (h, idx) {
        var stopObj = {
            label:      'Stop ' + (h.stop_number || (idx + 1)) + ' — Charge Here',
            name:       h.name,
            lat:        h.lat,
            lon:        h.lon,
            arrive_pct: h.arrive_pct !== undefined ? h.arrive_pct : 10,
            depart_pct: h.depart_pct || 80,
            segment_km: h.dist_from_start || 0,
            will_run_out: !!h.will_run_out,
        };
        _addStopMarker(h.lat, h.lon, h.stop_number || (idx + 1), stopObj, true);
    });

    updateBadge(hops.length + ' recommended stop(s)', 'bg-orange-100 text-orange-800');
}

function _addStopMarker(lat, lon, number, stop, isPlanMarker) {
    var color = stop.will_run_out ? '#dc2626' : (isPlanMarker ? '#d97706' : '#d97706');
    var icon  = L.divIcon({
        className: '',
        html: '<div style="background:' + color + ';color:#fff;border-radius:50%;width:32px;height:32px;'
            + 'display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:15px;'
            + 'border:2px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,0.4);cursor:pointer;">'
            + number + '</div>',
        iconSize: [32, 32], iconAnchor: [16, 16], popupAnchor: [0, -20],
    });

    var m = L.marker([lat, lon], { icon: icon, zIndexOffset: 1000 }).addTo(map);

    var journeyHtml = '';
    if (stop.arrive_pct !== undefined) {
        journeyHtml = '<hr style="margin:6px 0">'
            + '<p style="font-size:11px;font-weight:600;color:#374151;margin:0 0 4px;">Journey Plan</p>'
            + '<p style="font-size:11px;margin:0;">🔋 Arrive here: <b>' + stop.arrive_pct + '%</b></p>'
            + '<p style="font-size:11px;margin:2px 0 0;">⚡ Charge to: <b>' + stop.depart_pct + '%</b></p>'
            + (stop.will_run_out
                ? '<p style="font-size:11px;color:#dc2626;margin:4px 0 0;">❌ Battery may run out — charge before leaving!</p>'
                : '<p style="font-size:11px;color:#16a34a;margin:4px 0 0;">✅ Safe arrival with ' + stop.arrive_pct + '%</p>');
    }

    m.bindPopup(
        '<b style="color:' + color + ';">' + (stop.label || 'Charging Stop') + '</b><br>'
        + '<b>' + stop.name + '</b><br>'
        + (stop.segment_km ? '📍 ' + stop.segment_km + ' km from start<br>' : '')
        + journeyHtml
        + '<button onclick="rerouteViaStation(' + lat + ',' + lon + ')" '
        + 'style="margin-top:8px;width:100%;background:#2563eb;color:#fff;border:none;'
        + 'padding:5px 8px;border-radius:4px;cursor:pointer;font-size:11px;">'
        + '🗺️ Reroute via this station</button>'
    );

    if (number === 1) setTimeout(function () { m.openPopup(); }, 600);
    stationMarkers.push(m);
}

// ── Alternative stations (small icons) ───────────────────────────────────────

function renderAlternativeStations(altStations, recommendedStops) {
    altMarkers.forEach(function (m) { map.removeLayer(m); });
    altMarkers = [];

    if (!altStations || altStations.length === 0) return;

    var recSet = new Set((recommendedStops || []).map(function (s) { return s.lat + ',' + s.lon; }));

    altStations.forEach(function (s) {
        if (recSet.has(s.lat + ',' + s.lon)) return;

        var needsCharge = !s.reachable && s.charge_at_home != null;
        var iconCls     = s.reachable ? '' : (needsCharge ? 'home-charge-icon' : 'grayscale-icon');
        var icon = L.icon({
            iconUrl: 'images/icon.jpg', iconSize: [28, 28],
            iconAnchor: [14, 28], popupAnchor: [0, -30], className: iconCls,
        });
        var m = L.marker([s.lat, s.lon], { icon: icon, zIndexOffset: 400 }).addTo(map);

        var statusHtml, btnHtml;
        if (s.reachable) {
            statusHtml = '<p style="color:#16a34a;font-size:11px;margin:4px 0;">✅ Reachable — arrive with <b>' + s.arrive_pct + '%</b></p>';
            btnHtml    = '<button onclick="rerouteViaStation(' + s.lat + ',' + s.lon + ')" '
                + 'style="background:#2563eb;color:#fff;border:none;padding:3px 8px;border-radius:4px;cursor:pointer;font-size:11px;">'
                + 'Reroute via here</button>';
        } else {
            statusHtml = '<p style="color:#d97706;font-size:11px;margin:4px 0;">🏠 Charge at home to <b>' + s.charge_at_home + '%</b> to reach</p>';
            btnHtml    = '<button onclick="rerouteViaStation(' + s.lat + ',' + s.lon + ')" '
                + 'style="background:#d97706;color:#fff;border:none;padding:3px 8px;border-radius:4px;cursor:pointer;font-size:11px;">'
                + 'Reroute via here</button>';
        }

        m.bindPopup('<b>' + s.name + '</b><br>📍 ' + s.segment_km + ' km<br>' + statusHtml + btnHtml);
        altMarkers.push(m);
    });
}

// ── City station icons (pre-loaded for city) ──────────────────────────────────

async function fetchStationsForCity(city) {
    updateBadge('Finding Chargers in ' + city + '...', 'bg-yellow-100 text-yellow-800');
    var coords = cityCoords[city] || { lat: 12.9716, lon: 77.5946 };
    var lat    = coords.lat, lon = coords.lon;

    try {
        var ctrl = new AbortController();
        var tid  = setTimeout(function () { ctrl.abort(); }, 35000);
        var res  = await fetch(API_URL + '/charging-stations?city=' + city, { signal: ctrl.signal });
        clearTimeout(tid);
        if (!res.ok) throw new Error('non-ok');
        var raw = await res.json();
        if (!raw || raw.length === 0) throw new Error('empty');
        allCityStations = raw;
        renderStations(allCityStations);
        return;
    } catch (e) {
        console.warn('Backend stations failed, trying Overpass:', e.message);
    }

    try {
        var q = '[out:json][timeout:30];(node["amenity"="charging_station"](around:30000,' + lat + ',' + lon + '););out center;';
        var res2 = await fetch('https://overpass-api.de/api/interpreter?data=' + encodeURIComponent(q));
        var data = await res2.json();
        allCityStations = (data.elements || []).reduce(function (acc, el) {
            var slat = el.lat || (el.center && el.center.lat);
            var slon = el.lon || (el.center && el.center.lon);
            if (slat && slon) acc.push({ lat: slat, lon: slon, name: (el.tags && el.tags.name) || 'Public Charger' });
            return acc;
        }, []);
        if (allCityStations.length > 0) renderStations(allCityStations);
        else updateBadge('No stations found', 'bg-gray-100 text-gray-800');
    } catch (e) {
        console.error('Overpass failed:', e);
        updateBadge('Could not load stations', 'bg-red-100 text-red-800');
    }
}

function renderStations(stations) {
    cityStationMarkers.forEach(function (m) { map.removeLayer(m); });
    cityStationMarkers = [];
    if (!stations || stations.length === 0) {
        updateBadge('No Chargers Found', 'bg-gray-100 text-gray-800');
        return;
    }
    var icon = L.icon({ iconUrl: 'images/icon.jpg', iconSize: [30, 30], iconAnchor: [15, 30], popupAnchor: [0, -32] });
    stations.forEach(function (s) {
        var m = L.marker([s.lat, s.lon], { icon: icon }).addTo(map);
        m.bindPopup('<b>' + s.name + '</b><br>EV Charging Station<br>'
            + '<button onclick="rerouteViaStation(' + s.lat + ',' + s.lon + ')" '
            + 'style="margin-top:5px;background:#2563eb;color:#fff;border:none;padding:3px 8px;border-radius:4px;cursor:pointer;font-size:11px;">'
            + 'Reroute via here</button>');
        cityStationMarkers.push(m);
    });
    updateBadge(stations.length + ' stations in city', 'bg-green-100 text-green-800');
}
