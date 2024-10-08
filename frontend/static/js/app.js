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
    const nextThemeButton = document.getElementById('nextThemeButton');
    nextThemeButton.addEventListener('click', async () => {
        const response = await fetch('/api/set_theme', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ next_theme: true }),
        });
        const result = await response.json();
        console.log('Next theme set:', result);
    });

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
    const brightnessSlider = document.getElementById('brightness-slider');
    const brightnessValue = document.getElementById('brightness-value');

    brightnessSlider.addEventListener('input', async () => {
        const brightness = parseFloat(brightnessSlider.value);
        brightnessValue.textContent = `${Math.round(brightness * 100)}%`;
        const response = await api.setMasterBrightness(brightness);
        console.log('Brightness set:', response);
    });

    // Initialize brightness value display
    brightnessValue.textContent = `${Math.round(brightnessSlider.value * 100)}%`;

    // Theme control sliders
    const themeControls = {
        'transition-speed': 0.08,
        'color-variation': 0.9,
        'intensity-fluctuation': 0.6,
        'color-wheel-speed': 0.2,
        'wave-effect': 0.7
    };

    Object.keys(themeControls).forEach(controlId => {
        const slider = document.getElementById(controlId);
        const valueDisplay = document.getElementById(`${controlId}-value`);
        
        if (slider && valueDisplay) {
            slider.value = themeControls[controlId];
            valueDisplay.textContent = themeControls[controlId];

            slider.addEventListener('input', async () => {
                const value = parseFloat(slider.value);
                valueDisplay.textContent = value.toFixed(2);
                const response = await api.updateThemeValue(controlId, value);
                console.log(`${controlId} updated:`, response);
            });
        } else {
            console.warn(`Element not found for theme control: ${controlId}`);
        }
    });

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
        try {
            const response = await api.getLightFixtures();
            return `<pre>${response}</pre>`;
        } catch (error) {
            console.error('Error fetching light fixtures:', error);
            return '<p class="error-message">Error fetching light fixtures. Please check the console for details.</p>';
        }
    }, () => generateCurlCommand('GET', 'light_fixtures'));
    apiControls.appendChild(showLightFixturesControl);

    // Connected Clients Display
    const showConnectedClientsControl = createControl('Connected Clients', async () => {
        try {
            const clients = await api.getConnectedClients();
            return createClientList(clients);
        } catch (error) {
            console.error('Error fetching connected clients:', error);
            return 'Error fetching connected clients. Please check the console for details.';
        }
    }, () => generateCurlCommand('GET', 'connected_clients'));
    apiControls.appendChild(showConnectedClientsControl);

    function createClientList(clients) {
        let listHTML = '<table class="client-list"><thead><tr><th>Name</th><th>IP</th><th>Rooms</th><th>Action</th></tr></thead><tbody>';
        clients.forEach(client => {
            listHTML += `
                <tr>
                    <td>${client.name}</td>
                    <td>${client.ip}</td>
                    <td>${client.rooms.join(', ')}</td>
                    <td><button class="terminate-button" data-ip="${client.ip}">Terminate</button></td>
                </tr>
            `;
        });
        listHTML += '</tbody></table>';

        // Add event listeners for terminate buttons
        setTimeout(() => {
            document.querySelectorAll('.terminate-button').forEach(button => {
                button.addEventListener('click', async (e) => {
                    const ip = e.target.getAttribute('data-ip');
                    try {
                        await api.terminateClient(ip);
                        e.target.closest('tr').remove();
                    } catch (error) {
                        console.error('Error terminating client:', error);
                        alert('Failed to terminate client. Check console for details.');
                    }
                });
            });
        }, 0);

        return listHTML;
    }

    // Kill Process Button
    const killProcessControl = createControl('Kill Process', async () => {
        if (confirm('Are you sure you want to kill the entire process? This will stop all operations.')) {
            try {
                const response = await api.killProcess();
                return JSON.stringify(response);
            } catch (error) {
                console.error('Error killing process:', error);
                return '<p>Error killing process. Please check the console for details.</p>';
            }
        }
        return 'Operation cancelled';
    });
    apiControls.appendChild(killProcessControl);

});

function createControl(title, action, getCurlCommand) {
    const control = document.createElement('div');
    control.className = 'api-control';
    control.innerHTML = `
        <h2>${title}</h2>
        <button>Execute</button>
        <pre class="response"></pre>
        <div class="curl-command"></div>
    `;
    control.querySelector('button').addEventListener('click', async () => {
        const responseElement = control.querySelector('.response');
        const curlElement = control.querySelector('.curl-command');
        try {
            const result = await action();
            responseElement.innerHTML = result;
            curlElement.innerHTML = `Curl equivalent: ${getCurlCommand()}`;
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
    return `<pre class="curl-command">${curlCommand}</pre>`;
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

function createTable(data, columns) {
    let tableHTML = '<div class="table-container"><table class="themed-table">';
    
    // Create header
    tableHTML += '<thead><tr>';
    columns.forEach(column => {
        tableHTML += `<th>${column.charAt(0).toUpperCase() + column.slice(1)}</th>`;
    });
    tableHTML += '</tr></thead>';

    // Create body
    tableHTML += '<tbody>';
    data.forEach(item => {
        tableHTML += '<tr>';
        columns.forEach(column => {
            let value = item[column];
            if (Array.isArray(value)) {
                value = value.join(', ');
            }
            tableHTML += `<td>${value}</td>`;
        });
        tableHTML += '</tr>';
    });
    tableHTML += '</tbody></table></div>';

    return tableHTML;
}
