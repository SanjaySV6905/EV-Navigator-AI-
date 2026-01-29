function updateSummary(dist, energy) {
    const resultsDiv = document.getElementById('results');
    resultsDiv.classList.remove('hidden');

    document.getElementById('resDist').innerText = `${dist.toFixed(2)} km`;
    document.getElementById('resEnergy').innerText = `${energy.toFixed(2)} kWh`;
    
    const cap = parseFloat(document.getElementById('batteryCap').value);
    const level = parseFloat(document.getElementById('batteryLevel').value);
    const currentEnergy = cap * (level / 100);
    const remainingEnergy = currentEnergy - energy;
    const remainingPercent = (remainingEnergy / cap) * 100;
    
    const chargingNeeded = energy > currentEnergy;
    const alertBox = document.getElementById('resAlert');
    const remEl = document.getElementById('resRemaining');
    
    remEl.innerText = `${remainingPercent.toFixed(1)}%`;
    remEl.className = remainingPercent < 0 ? 'font-bold text-red-600' : 'font-bold text-green-600';

    alertBox.className = chargingNeeded 
        ? "p-2 rounded mt-2 text-center text-sm font-bold bg-red-100 text-red-700" 
        : "p-2 rounded mt-2 text-center text-sm font-bold bg-green-100 text-green-700";
    alertBox.innerText = chargingNeeded ? "⚠️ Charging Needed!" : "✅ Battery Sufficient";
}

function updateBadge(text, classes) {
    const badge = document.getElementById('stationCount');
    badge.classList.remove('hidden');
    badge.innerText = text;
    badge.className = `stat-badge ${classes}`;
}

function showSpinner() {
    document.getElementById('spinner').classList.remove('hidden');
}

function hideSpinner() {
    document.getElementById('spinner').classList.add('hidden');
}

function hideResults() {
    document.getElementById('results').classList.add('hidden');
}