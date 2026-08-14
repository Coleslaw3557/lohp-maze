"""Manual API smoke test. Run against a live server:

    LOHP_SERVER=http://192.168.252.231:5000 python test_api.py

Requires the `requests` package (not in requirements.txt; dev-only).
"""
import json
import os
import time

import requests

BASE_URL = os.environ.get('LOHP_SERVER', 'http://localhost:5000') + '/api'


def run_test(test_func):
    try:
        test_func()
        print(f"{test_func.__name__} - Success")
        return True
    except AssertionError as e:
        print(f"{test_func.__name__} - Failed: {e}")
    except Exception as e:
        print(f"{test_func.__name__} - Error: {e}")
    return False


def get_json(path, expect_dict=True):
    response = requests.get(f"{BASE_URL}/{path}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    if expect_dict:
        assert isinstance(data, dict) and data, f"Expected a non-empty dict from /{path}"
    return data


def test_get_rooms():
    print(json.dumps(get_json('rooms'), indent=2))


def test_get_effects():
    print(json.dumps(get_json('effects_list'), indent=2))


def test_get_themes():
    print(json.dumps(get_json('themes'), indent=2))


def test_get_light_models():
    print(json.dumps(get_json('light_models'), indent=2))


def post_success(path, payload):
    response = requests.post(f"{BASE_URL}/{path}", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    result = response.json()
    print(result)
    return result


def test_set_theme():
    post_success('set_theme', {"theme_name": "DeepCanopy"})


def test_run_effect():
    post_success('run_effect', {"room": "Entrance", "effect_name": "Lightning"})


def test_set_master_brightness():
    result = post_success('set_master_brightness', {"brightness": 0.8})
    assert result["master_brightness"] == 0.8


def test_run_channel_test():
    post_success('run_test', {
        "testType": "channel",
        "rooms": ["Entrance"],
        "channelValues": {"total_dimming": 255, "r_dimming": 255, "g_dimming": 0, "b_dimming": 0}
    })


def test_run_effect_test():
    post_success('run_test', {"testType": "effect", "rooms": ["Entrance"], "effectName": "Lightning"})


def test_stop_test():
    post_success('stop_test', {})


def test_sound_mode():
    state = get_json('sound_mode')
    assert state['mode'] in state['modes'], f"mode {state['mode']} not in {state['modes']}"
    assert 'unattended' in state['modes'] and 'attended' in state['modes']
    assert post_success('sound_mode', {"mode": "attended"})['mode'] == 'attended'
    assert get_json('sound_mode')['mode'] == 'attended'
    assert post_success('sound_mode', {"mode": "unattended"})['mode'] == 'unattended'
    response = requests.post(f"{BASE_URL}/sound_mode", json={"mode": "party"})
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"


if __name__ == "__main__":
    print(f"Starting API tests against {BASE_URL}")
    tests = [
        (test_get_rooms, 0),
        (test_get_effects, 0),
        (test_get_themes, 0),
        (test_get_light_models, 0),
        (test_set_theme, 2),
        (test_run_effect, 5),
        (test_set_master_brightness, 2),
        (test_run_channel_test, 5),
        (test_run_effect_test, 5),
        (test_stop_test, 0),
        (test_sound_mode, 0),
    ]
    results = []
    for test, wait in tests:
        results.append(run_test(test))
        if wait:
            time.sleep(wait)
    print(f"\n{results.count(True)}/{len(results)} tests passed")
