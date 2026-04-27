let debounceTimer;

// City bounding boxes to restrict Nominatim results
const cityBounds = {
    "Bangalore": { viewbox: "77.4,12.8,77.8,13.2", bounded: 1 },
    "Chennai":   { viewbox: "80.1,12.8,80.4,13.3", bounded: 1 }
};

function setupAutocomplete() {
    ['start', 'end'].forEach(type => {
        document.getElementById(`${type}Addr`).addEventListener('input', () => handleAddressInput(type));
    });
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.relative')) {
            document.querySelectorAll('.suggestions-list').forEach(el => el.classList.add('hidden'));
        }
    });
}

function handleAddressInput(type) {
    clearTimeout(debounceTimer);
    const inputVal = document.getElementById(`${type}Addr`).value;
    const suggestionsBox = document.getElementById(`${type}Suggestions`);
    if (inputVal.length < 3) { suggestionsBox.classList.add('hidden'); return; }
    debounceTimer = setTimeout(() => fetchSuggestions(inputVal, type), 350);
}

async function fetchSuggestions(query, type) {
    try {
        const city   = document.getElementById('city').value;
        const bounds = cityBounds[city] || cityBounds["Bangalore"];

        // Nominatim search — much more accurate for Indian addresses
        const url = `https://nominatim.openstreetmap.org/search?` +
            `q=${encodeURIComponent(query + ', ' + city + ', India')}` +
            `&format=json&addressdetails=1&limit=6` +
            `&viewbox=${bounds.viewbox}&bounded=${bounds.bounded}` +
            `&accept-language=en`;

        const res  = await fetch(url, { headers: { 'Accept-Language': 'en' } });
        const data = await res.json();
        showSuggestions(data, type);
    } catch (error) {
        console.error("Autocomplete error:", error);
    }
}

function showSuggestions(results, type) {
    const box = document.getElementById(`${type}Suggestions`);
    box.innerHTML = '';
    if (!results || results.length === 0) { box.classList.add('hidden'); return; }

    results.forEach(item => {
        const addr    = item.address || {};
        // Build a clean display name
        const main    = addr.road || addr.neighbourhood || addr.suburb || item.name || item.display_name.split(',')[0];
        const subParts = [];
        if (addr.suburb && addr.suburb !== main)      subParts.push(addr.suburb);
        if (addr.city_district)                        subParts.push(addr.city_district);
        if (addr.city || addr.town || addr.village)    subParts.push(addr.city || addr.town || addr.village);
        const sub = subParts.join(', ');

        const div = document.createElement('div');
        div.className = 'suggestion-item';
        div.innerHTML = `<div>${main}</div><div class="suggestion-sub">${sub}</div>`;
        div.onclick = () => selectAddress(`${main}${sub ? ', ' + sub : ''}`, parseFloat(item.lat), parseFloat(item.lon), type);
        box.appendChild(div);
    });
    box.classList.remove('hidden');
}

function selectAddress(displayName, lat, lon, type) {
    document.getElementById(`${type}Addr`).value = displayName;
    document.getElementById(`${type}Lat`).value  = lat;
    document.getElementById(`${type}Lon`).value  = lon;
    document.getElementById(`${type}Suggestions`).classList.add('hidden');
}
