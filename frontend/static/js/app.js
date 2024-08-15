document.addEventListener('DOMContentLoaded', async () => {
    const apiControls = document.getElementById('api-controls');
    const rooms = await api.getRooms();
    const effects = await api.getEffects();
    const themes = await api.getThemes();

    // Set Theme
    const setThemeControl = createControl('Set Theme', async () => {
        const themeSelect = document.getElementById('theme-select');
        const response = await api.setTheme(themeSelect.value);
        return JSON.stringify(response);
    }, () => generateCurlCommand('POST', 'set_theme', { theme_name: document.getElementById('theme-select').value }));
    const themeSelect = createSelect('theme-select', Object.keys(themes));
    setThemeControl.insertBefore(themeSelect, setThemeControl.querySelector('button'));
    apiControls.appendChild(setThemeControl);

    // Set Next Theme
    const setNextThemeControl = createControl('Set Next Theme', async () => {
        const response = await api.setTheme(null, true);
        return JSON.stringify(response);
    }, () => generateCurlCommand('POST', 'set_theme', { next_theme: true }));
    apiControls.appendChild(setNextThemeControl);

    // Run Effect
    const runEffectControl = createControl('Run Effect', async () => {
        const roomSelect = document.getElementById('room-select');
        const effectSelect = document.getElementById('effect-select');
        const response = await api.runEffect(roomSelect.value, effectSelect.value);
        return JSON.stringify(response);
    }, () => generateCurlCommand('POST', 'run_effect', { room: document.getElementById('room-select').value, effect_name: document.getElementById('effect-select').value }));
    const roomSelect = createSelect('room-select', Object.keys(rooms));
    const effectSelect = createSelect('effect-select', Object.keys(effects));
    runEffectControl.insertBefore(createLabel('Room:', roomSelect), runEffectControl.querySelector('button'));
    runEffectControl.insertBefore(createLabel('Effect:', effectSelect), runEffectControl.querySelector('button'));
    apiControls.appendChild(runEffectControl);

    // Set Master Brightness
    const setBrightnessControl = createControl('Set Master Brightness', async () => {
        const brightnessInput = document.getElementById('brightness-input');
        const response = await api.setMasterBrightness(parseFloat(brightnessInput.value));
        return JSON.stringify(response);
    }, () => generateCurlCommand('POST', 'set_master_brightness', { brightness: parseFloat(document.getElementById('brightness-input').value) }));
    const brightnessInput = document.createElement('input');
    brightnessInput.type = 'number';
    brightnessInput.id = 'brightness-input';
    brightnessInput.min = '0';
    brightnessInput.max = '1';
    brightnessInput.step = '0.1';
    brightnessInput.value = '1';
    setBrightnessControl.insertBefore(createLabel('Brightness:', brightnessInput), setBrightnessControl.querySelector('button'));
    apiControls.appendChild(setBrightnessControl);

    // Start Music
    apiControls.appendChild(createControl('Start Music', async () => {
        const response = await api.startMusic();
        return JSON.stringify(response);
    }, () => generateCurlCommand('POST', 'start_music')));

    // Stop Music
    apiControls.appendChild(createControl('Stop Music', async () => {
        const response = await api.stopMusic();
        return JSON.stringify(response);
    }, () => generateCurlCommand('POST', 'stop_music')));

    // Light Fixtures Table
    const showLightFixturesControl = createControl('Show Light Fixtures', async () => {
        const fixtures = await api.getLightFixtures();
        let tableHTML = '<table><tr><th>Room</th><th>Model</th><th>Start Address</th></tr>';
        fixtures.forEach(fixture => {
            tableHTML += `<tr><td>${fixture.room}</td><td>${fixture.model}</td><td>${fixture.start_address}</td></tr>`;
        });
        tableHTML += '</table>';
        return tableHTML;
    });
    apiControls.appendChild(showLightFixturesControl);

    // Connected Clients Table
    const showConnectedClientsControl = createControl('Show Connected Clients', async () => {
        const clients = await api.getConnectedClients();
        let tableHTML = '<table><tr><th>Name</th><th>IP</th><th>Associated Rooms</th></tr>';
        clients.forEach(client => {
            tableHTML += `<tr><td>${client.name}</td><td>${client.ip}</td><td>${client.rooms.join(', ')}</td></tr>`;
        });
        tableHTML += '</table>';
        return tableHTML;
    });
    apiControls.appendChild(showConnectedClientsControl);

    // Kill Process Button
    const killProcessControl = createControl('Kill Process', async () => {
        if (confirm('Are you sure you want to kill the entire process? This will stop all operations.')) {
            const response = await api.killProcess();
            return JSON.stringify(response);
        }
        return 'Operation cancelled';
    });
    apiControls.appendChild(killProcessControl);

    // Show Room Layout and Light Fixtures
    const showRoomLayoutControl = createControl('Show Room Layout and Light Fixtures', async () => {
        const roomLayout = await api.getRoomLayout();
        let layoutHTML = '<h3>Room Layout and Light Fixtures</h3>';
        for (const [room, fixtures] of Object.entries(roomLayout)) {
            layoutHTML += `<h4>${room}</h4><ul>`;
            fixtures.forEach(fixture => {
                layoutHTML += `<li>Model: ${fixture.model}, Start Address: ${fixture.start_address}</li>`;
            });
            layoutHTML += '</ul>';
        }
        return layoutHTML;
    });
    apiControls.appendChild(showRoomLayoutControl);
});

function createControl(title, action, getCurlCommand) {
    const control = document.createElement('div');
    control.className = 'api-control';
    control.innerHTML = `
        <h2>${title}</h2>
        <button>Execute</button>
        <div class="response"></div>
        <div class="curl-command"></div>
    `;
    control.querySelector('button').addEventListener('click', async () => {
        const responseElement = control.querySelector('.response');
        const curlElement = control.querySelector('.curl-command');
        try {
            const result = await action();
            responseElement.textContent = result;
            curlElement.textContent = `Curl equivalent: ${getCurlCommand()}`;
        } catch (error) {
            responseElement.textContent = `Error: ${error.message}`;
            curlElement.textContent = '';
        }
    });
    return control;
}

function generateCurlCommand(method, endpoint, data = null) {
    let curlCommand = `curl -X ${method} http://localhost:5000/api/${endpoint}`;
    if (data) {
        curlCommand += ` -H "Content-Type: application/json" -d '${JSON.stringify(data)}'`;
    }
    return curlCommand;
}

function createSelect(id, options) {
    const select = document.createElement('select');
    select.id = id;
    options.forEach(option => {
        const optionElement = document.createElement('option');
        optionElement.value = option;
        optionElement.textContent = option;
        select.appendChild(optionElement);
    });
    return select;
}

function createLabel(text, element) {
    const label = document.createElement('label');
    label.textContent = text;
    label.appendChild(element);
    return label;
}
