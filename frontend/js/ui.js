/* ============================================================
   ui.js — EV Router UI  (matches new backend smart-plan format)
   ============================================================ */

var _lastRouteData = null;  // kept for the plan-toggle switcher

function updateSummary(dist, energy, data) {
    _lastRouteData = data;
    document.getElementById('results').classList.remove('hidden');

    document.getElementById('resDist').innerText   = dist.toFixed(1) + ' km';
    document.getElementById('resEnergy').innerText = energy.toFixed(2) + ' kWh';

    var now    = new Date();
    var durMin = data.total_duration_min || 0;
    document.getElementById('resDuration').innerText   = formatDuration(durMin);
    document.getElementById('resDepartTime').innerText = formatTime(now);
    document.getElementById('resArrivalTime').innerText = formatTime(new Date(now.getTime() + durMin * 60000));

    var cap      = parseFloat(document.getElementById('batteryCap').value) || 40;
    var level    = parseFloat(document.getElementById('batteryLevel').value) || 50;
    var finalPct = (data.final_battery_pct !== undefined)
        ? data.final_battery_pct
        : Math.max(((cap * level / 100) - energy) / cap * 100, 0);

    // If charging is needed and a plan guarantees ≥10%, compute the EXACT destination %
    // from the last hop's depart_pct minus the cost of the final leg to destination.
    var activePlan = data.opt_a_home_charge_plan || data.opt_b_nearest_station_plan;
    var hasPlan    = activePlan && (activePlan.hops || []).length > 0;
    if (data.charging_needed && finalPct < 10 && hasPlan) {
        var lastHop   = activePlan.hops[activePlan.hops.length - 1];
        var kwhPerKm  = (energy > 0 && dist > 0) ? energy / dist : 0;
        var lastLegKm = Math.max(dist - (lastHop.dist_from_start || 0), 0.1);
        var lastLegPct = cap > 0 ? (kwhPerKm * lastLegKm / cap * 100) : 0;
        finalPct = Math.max(Math.round((lastHop.depart_pct || 10) - lastLegPct), 10);
    }

    var remEl = document.getElementById('resRemaining');
    remEl.innerText   = finalPct > 0 ? finalPct.toFixed(0) + '%' : '0% ⚠️';
    remEl.style.color = finalPct < 10 ? '#dc2626' : '#16a34a';

    // remove old panel
    var old = document.getElementById('chargingPlanPanel');
    if (old) old.remove();

    var alertBox = document.getElementById('resAlert');
    var panel    = document.createElement('div');
    panel.id     = 'chargingPlanPanel';
    panel.style.marginTop = '8px';

    // ── Case 1: Direct stops on route ────────────────────────────────────────
    if (data.charging_stops && data.charging_stops.length > 0) {
        alertBox.innerHTML = '<div class="alert-warn">⚠️ Charging needed — '
            + data.charging_stops.length + ' stop(s) planned on route</div>';
        panel.innerHTML = _renderDirectStops(data.charging_stops, finalPct, durMin, now);

    // ── Case 2: Charging needed but no stops found on direct route ───────────
    } else if (data.charging_needed) {
        alertBox.innerHTML = '<div class="alert-info">⚠️ Charging needed — please choose a plan below</div>';
        panel.innerHTML = _renderPlanToggle(data);

    // ── Case 3: No charging needed ────────────────────────────────────────────
    } else {
        alertBox.innerHTML = '<div class="alert-ok">✅ Battery sufficient — no charging needed!</div>';
        panel.innerHTML = '<div style="font-size:11px;color:#64748b;margin-top:6px;">'
            + '💡 Optional stations shown on map — click any to reroute through it.</div>';
    }

    alertBox.after(panel);
}

// ── Direct route stops card ───────────────────────────────────────────────────
function _renderDirectStops(stops, finalPct, totalMin, now) {
    var html = '<div class="charge-plan-title">⚡ Charging Plan</div>';
    var cumulDrive = 0;
    stops.forEach(function (s) {
        var driveMin  = s.time_to_station_min || 0;
        var chargeMin = s.charging_time_min   || 45;
        cumulDrive += driveMin;
        var arrETA = formatTime(new Date(now.getTime() + cumulDrive * 60000));
        var depETA = formatTime(new Date(now.getTime() + (cumulDrive + chargeMin) * 60000));
        var warnHtml = s.will_run_out
            ? '<div class="cs-pill red" style="margin-top:6px;display:inline-block;">❌ Battery may run out before here!</div>'
            : '';
        html += '<div class="charge-stop-card">'
            + '<div class="cs-name">' + s.label + '</div>'
            + '<div class="cs-sub">'  + s.name  + '</div>'
            + '<div class="cs-pills">'
            +   '<span class="cs-pill">📍 ' + s.segment_km + ' km</span>'
            +   '<span class="cs-pill blue">🔋 Arrive ' + s.arrive_pct + '%</span>'
            +   '<span class="cs-pill green">⚡ Charge to ' + s.depart_pct + '%</span>'
            + '</div>'
            + '<div class="cs-pills" style="margin-top:4px;">'
            +   '<span class="cs-pill blue">🕐 ' + arrETA   + '</span>'
            +   '<span class="cs-pill">⏱️ '         + chargeMin + ' min</span>'
            +   '<span class="cs-pill green">🚀 ' + depETA   + '</span>'
            + '</div>'
            + warnHtml
            + '<button onclick="rerouteViaStation(' + s.lat + ',' + s.lon + ')" '
            + 'style="margin-top:6px;width:100%;background:#2563eb;color:#fff;border:none;padding:4px 8px;border-radius:4px;cursor:pointer;font-size:11px;">'
            + '🗺️ Reroute via this station only</button>'
            + '</div>';
        cumulDrive += chargeMin;
    });
    var chargingTot = stops.length * 45;
    var driveOnly   = (totalMin || 0) - chargingTot;
    html += '<div style="font-size:11px;color:#64748b;margin-top:6px;">'
        + '🕐 Drive <b>' + formatDuration(driveOnly) + '</b>'
        + ' + Charging <b>' + chargingTot + ' min</b>'
        + ' = <b>' + formatDuration(totalMin) + '</b> total</div>';
    html += '<div style="font-size:12px;color:#16a34a;font-weight:700;margin-top:4px;">'
        + '🏁 Arrive with ~' + finalPct.toFixed(0) + '% battery</div>';
    return html;
}

// ── Plan A / B toggle ─────────────────────────────────────────────────────────
function _renderPlanToggle(data) {
    var planA = data.opt_a_home_charge_plan;
    var planB = data.opt_b_nearest_station_plan;
    if (!planA && !planB) {
        return '<div style="font-size:11px;color:#78716c;">No charging plan could be calculated. Try enabling more stations.</div>';
    }

    var html = '<div class="plan-toggle-row">'
        + '<button id="btnPlanHome" class="plan-toggle active" onclick="showPlan(\'home\')">🏠 Charge at Home</button>'
        + '<button id="btnPlanStation" class="plan-toggle" onclick="showPlan(\'station\')">⚡ Go Charge First</button>'
        + '</div>';

    // Plan A panel
    html += '<div id="planHome" class="journey-card">';
    if (planA) {
        html += '<div class="jc-title">🏠 Option A — Plan from Home</div>'
            + '<div style="font-size:13px;font-weight:700;color:#1e3a8a;margin-bottom:8px;">'
            + '🔌 ' + (planA.start_action || '') + '</div>';
        html += _renderHopList(planA.hops || [], 'home');
    } else {
        html += '<div style="font-size:11px;color:#78716c;">No home charge plan available.</div>';
    }
    html += '</div>';

    // Plan B panel
    html += '<div id="planStation" class="journey-card" style="display:none;">';
    if (planB) {
        html += '<div class="jc-title">⚡ Option B — Go to Station First</div>';

        // Prominent home charge instruction box
        var needsHomeCharge = planB.hops && planB.hops[0] && planB.hops[0].home_charge_needed;
        var homeChargePct   = planB.charge_at_home_pct || (planB.hops && planB.hops[0] && planB.hops[0].home_charge_pct);
        if (needsHomeCharge && homeChargePct) {
            html += '<div style="background:#fef3c7;border:2px solid #f59e0b;border-radius:10px;padding:10px 12px;margin-bottom:10px;">'
                + '<div style="font-size:11px;font-weight:700;color:#78350f;text-transform:uppercase;letter-spacing:.04em;">🏠 Step 1 — Before you leave home</div>'
                + '<div style="font-size:15px;font-weight:800;color:#92400e;margin-top:4px;">'
                + '🔌 Charge your EV to <span style="color:#b45309;font-size:17px;">' + homeChargePct.toFixed(0) + '%</span></div>'
                + '<div style="font-size:11px;color:#78350f;margin-top:3px;">'
                + 'This ensures you arrive at the nearest charger with a safe 10% buffer.'
                + '</div>'
                + '</div>';
        } else {
            html += '<div style="font-size:13px;font-weight:700;color:#92400e;margin-bottom:8px;">'
                + '⚡ ' + (planB.start_action || '') + '</div>';
        }

        html += _renderHopList(planB.hops || [], 'station');
    } else {
        html += '<div style="font-size:11px;color:#78716c;">No nearby fast-charger plan available.</div>';
    }
    html += '</div>';

    return html;
}

function _renderHopList(hops, planType) {
    if (!hops || hops.length === 0) {
        return '<div style="font-size:11px;color:#16a34a;">✅ Drive directly to destination!</div>';
    }
    var html = '';
    hops.forEach(function (h, i) {
        var warn = h.will_run_out
            ? '<div style="color:#dc2626;font-size:10px;margin-top:2px;">❌ Battery may run out on this leg!</div>' : '';

        // For Plan B stop 1: show the home-charge reminder inside the card
        var homeChargeTag = '';
        if (planType === 'station' && i === 0 && h.home_charge_needed && h.home_charge_pct) {
            homeChargeTag = '<div style="background:#fef9c3;border:1px solid #fde047;border-radius:6px;'
                + 'padding:4px 8px;font-size:11px;font-weight:700;color:#713f12;margin-bottom:5px;">'
                + '🏠 First charge at home to ' + h.home_charge_pct.toFixed(0) + '% before driving here'
                + '</div>';
        }

        html += '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px 10px;margin-bottom:8px;">'
            + homeChargeTag
            + '<div style="font-size:12px;font-weight:700;color:#1e293b;">📍 Stop ' + (h.stop_number || (i+1)) + ': ' + h.name + '</div>'
            + '<div style="font-size:11px;color:#64748b;margin-top:2px;">'
            +   h.dist_from_start + ' km from start'
            + '</div>'
            + '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:5px;">'
            +   '<span class="cs-pill blue">🔋 Arrive ' + (h.arrive_pct !== undefined ? h.arrive_pct : '~10') + '%</span>'
            +   '<span class="cs-pill green">⚡ Charge to ' + (h.depart_pct || '?') + '%</span>'
            +   (h.arrive_pct < 15 && !h.will_run_out ? '<span class="cs-pill" style="background:#fef3c7;color:#92400e;">Low on arrival!</span>' : '')
            + '</div>'
            + warn
            + '</div>';
    });

    // Build JSON for multi-reroute button
    var viaArr = hops.map(function (h) { return {lat: h.lat, lon: h.lon}; });
    html += '<div style="margin-top:4px;font-size:12px;color:#16a34a;font-weight:700;">🏁 Arrive destination with ≥10% battery</div>';
    html += '<button onclick=\'rerouteViaStations(' + JSON.stringify(viaArr) + ')\' '
        + 'style="margin-top:10px;width:100%;background:#2563eb;color:#fff;border:none;'
        + 'padding:8px;border-radius:6px;cursor:pointer;font-size:12px;font-weight:bold;">'
        + '🗺️ Reroute via all ' + hops.length + ' station(s)</button>';
    return html;
}

// ── Toggle ────────────────────────────────────────────────────────────────────
function showPlan(type) {
    var home = document.getElementById('planHome');
    var stn  = document.getElementById('planStation');
    var bH   = document.getElementById('btnPlanHome');
    var bS   = document.getElementById('btnPlanStation');
    if (!home || !stn) return;
    if (type === 'home') {
        home.style.display = ''; stn.style.display = 'none';
        bH.classList.add('active'); bS.classList.remove('active');
        if (window.renderActivePlanStations) window.renderActivePlanStations('home');
    } else {
        home.style.display = 'none'; stn.style.display = '';
        bH.classList.remove('active'); bS.classList.add('active');
        if (window.renderActivePlanStations) window.renderActivePlanStations('station');
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function updateBadge(text, classes) {
    var badge = document.getElementById('stationCount');
    badge.classList.remove('hidden');
    badge.innerText  = text;
    badge.className  = 'stat-badge ' + classes;
}

function formatDuration(mins) {
    if (!mins || mins < 1) return '0 min';
    if (mins < 60) return Math.round(mins) + ' min';
    var h = Math.floor(mins / 60), m = Math.round(mins % 60);
    return m > 0 ? h + 'h ' + m + 'm' : h + 'h';
}

function formatTime(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
}

function showSpinner() { document.getElementById('spinner').classList.remove('hidden'); }
function hideSpinner() { document.getElementById('spinner').classList.add('hidden'); }
function hideResults()  { document.getElementById('results').classList.add('hidden'); }
