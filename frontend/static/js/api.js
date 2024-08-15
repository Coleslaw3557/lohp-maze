const API_BASE_URL = '/api';

const api = {
    async getRooms() {
        const response = await fetch(`${API_BASE_URL}/rooms`);
        return response.json();
    },

    async getEffects() {
        const response = await fetch(`${API_BASE_URL}/effects_list`);
        return response.json();
    },

    async getThemes() {
        const response = await fetch(`${API_BASE_URL}/themes`);
        return response.json();
    },

    async setTheme(themeName) {
        const response = await fetch(`${API_BASE_URL}/set_theme`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ theme_name: themeName }),
        });
        return response.json();
    },

    async runEffect(room, effectName) {
        const response = await fetch(`${API_BASE_URL}/run_effect`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ room, effect_name: effectName }),
        });
        return response.json();
    },

    async setMasterBrightness(brightness) {
        const response = await fetch(`${API_BASE_URL}/set_master_brightness`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ brightness }),
        });
        return response.json();
    },

    async startMusic() {
        const response = await fetch(`${API_BASE_URL}/start_music`, {
            method: 'POST',
        });
        return response.json();
    },

    async stopMusic() {
        const response = await fetch(`${API_BASE_URL}/stop_music`, {
            method: 'POST',
        });
        return response.json();
    },

    async runEffectAllRooms(effectName) {
        const response = await fetch(`${API_BASE_URL}/run_effect_all_rooms`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ effect_name: effectName }),
        });
        return response.json();
    },

    async stopEffect(room) {
        const response = await fetch(`${API_BASE_URL}/stop_effect`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ room }),
        });
        return response.json();
    },
};
