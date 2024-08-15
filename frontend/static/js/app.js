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

    // Run Effect
    const runEffectControl = createControl('Run Effect', async () => {
        const roomSelect = document.getElementById('room-select');
        const effectSelect = document.getElementById('effect-select');
        const response = await api.runEffect(roomSelect.value, effectSelect.value);
        return JSON.stringify(response);
    });
    const roomSelect = createSelect('room-select', Object.keys(rooms));
    const effectSelect = createSelect('effect-select', Object.keys(effects));
    runEffectControl.insertBefore(effectSelect, runEffectControl.querySelector('button'));
    runEffectControl.insertBefore(roomSelect, effectSelect);
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
    setBrightnessControl.insertBefore(brightnessInput, setBrightnessControl.querySelector('button'));
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

    // Run Effect All Rooms
    const runEffectAllRoomsControl = createControl('Run Effect All Rooms', async () => {
        const allRoomsEffectSelect = document.getElementById('all-rooms-effect-select');
        const response = await api.runEffectAllRooms(allRoomsEffectSelect.value);
        return JSON.stringify(response);
    });
    const allRoomsEffectSelect = createSelect('all-rooms-effect-select', Object.keys(effects));
    runEffectAllRoomsControl.insertBefore(allRoomsEffectSelect, runEffectAllRoomsControl.querySelector('button'));
    apiControls.appendChild(runEffectAllRoomsControl);

    // Stop Effect
    const stopEffectControl = createControl('Stop Effect', async () => {
        const stopEffectRoomSelect = document.getElementById('stop-effect-room-select');
        const response = await api.stopEffect(stopEffectRoomSelect.value);
        return JSON.stringify(response);
    });
    const stopEffectRoomSelect = createSelect('stop-effect-room-select', [...Object.keys(rooms), 'all']);
    stopEffectControl.insertBefore(stopEffectRoomSelect, stopEffectControl.querySelector('button'));
    apiControls.appendChild(stopEffectControl);
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
