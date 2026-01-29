let debounceTimer;

function setupAutocomplete() {
    ['start', 'end'].forEach(type => {
        document.getElementById(`${type}Addr`).addEventListener('input', () => handleAddressInput(type));
    });

    // Close on click outside
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
    
    if (inputVal.length < 3) { 
        suggestionsBox.classList.add('hidden'); 
        return; 
    }

    debounceTimer = setTimeout(() => { fetchSuggestions(inputVal, type); }, 300);
}

async function fetchSuggestions(query, type) {
    try {
        const city = document.getElementById('city').value;
        const bias = cityCoords[city]; // uses cityCoords from main.js
        const url = `https://photon.komoot.io/api/?q=${encodeURIComponent(query)}&limit=5&lat=${bias.lat}&lon=${bias.lon}&lang=en`;
        
        const response = await fetch(url);
        const data = await response.json();
        
        showSuggestions(data.features, type);
    } catch (error) { 
        console.error("Autocomplete error:", error); 
    }
}

function showSuggestions(features, type) {
    const box = document.getElementById(`${type}Suggestions`);
    box.innerHTML = '';
    
    if (!features || features.length === 0) { 
        box.classList.add('hidden'); 
        return; 
    }

    features.forEach(feature => {
        const props = feature.properties;
        const coords = feature.geometry.coordinates; 
        
        let mainText = props.name || props.street || "Unknown Place";
        let subTextParts = [];
        if (props.street && props.street !== mainText) subTextParts.push(props.street);
        if (props.city) subTextParts.push(props.city);
        
        const subText = subTextParts.join(", ");
        
        const div = document.createElement('div');
        div.className = 'suggestion-item';
        div.innerHTML = `<div>${mainText}</div><div class="suggestion-sub">${subText}</div>`;
        div.onclick = () => {
            selectAddress(`${mainText}, ${subText}`, coords[1], coords[0], type);
        };
        box.appendChild(div);
    });
    
    box.classList.remove('hidden');
}

function selectAddress(displayName, lat, lon, type) {
    document.getElementById(`${type}Addr`).value = displayName;
    document.getElementById(`${type}Lat`).value = lat;
    document.getElementById(`${type}Lon`).value = lon;
    document.getElementById(`${type}Suggestions`).classList.add('hidden');
}