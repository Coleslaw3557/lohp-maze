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
    });
    const themeSelect = createSelect('theme-select', Object.keys(themes));
    setThemeControl.insertBefore(themeSelect, setThemeControl.querySelector('button'));
    apiControls.appendChild(setThemeControl);

    // Set Next Theme
    const setNextThemeControl = createControl('Set Next Theme', async () => {
        const response = await api.setTheme(null, true);
        return JSON.stringify(response);
    });
    apiControls.appendChild(setNextThemeControl);

    // Run Effect
    const runEffectControl = createControl('Run Effect', async () => {
        const roomSelect = document.getElementById('room-select');
        const effectSelect = document.getElementById('effect-select');
        const response = await api.runEffect(roomSelect.value, effectSelect.value);
        return JSON.stringify(response);
    });
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
    });
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
    }));

    // Stop Music
    apiControls.appendChild(createControl('Stop Music', async () => {
        const response = await api.stopMusic();
        return JSON.stringify(response);
    }));

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
});

function createControl(title, action) {
    const control = document.createElement('div');
    control.className = 'api-control';
    control.innerHTML = `
        <h2>${title}</h2>
        <button>Execute</button>
        <div class="response"></div>
    `;
    control.querySelector('button').addEventListener('click', async () => {
        const responseElement = control.querySelector('.response');
        try {
            responseElement.textContent = await action();
        } catch (error) {
            responseElement.textContent = `Error: ${error.message}`;
        }
    });
    return control;
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
