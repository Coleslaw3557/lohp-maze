import requests
import json
import time

BASE_URL = "http://192.168.1.238:5000/api"

def test_get_rooms():
    response = requests.get(f"{BASE_URL}/rooms")
    print("Get Rooms Response:", response.status_code)
    print(json.dumps(response.json(), indent=2))

def test_get_effects():
    response = requests.get(f"{BASE_URL}/effects")
    print("Get Effects Response:", response.status_code)
    print(json.dumps(response.json(), indent=2))

def test_get_themes():
    response = requests.get(f"{BASE_URL}/themes")
    print("Get Themes Response:", response.status_code)
    print(json.dumps(response.json(), indent=2))

def test_get_light_models():
    response = requests.get(f"{BASE_URL}/light_models")
    print("Get Light Models Response:", response.status_code)
    print(json.dumps(response.json(), indent=2))

def test_set_theme():
    theme_name = "Ocean"  # Assuming "Ocean" is a valid theme
    response = requests.post(f"{BASE_URL}/set_theme", json={"theme_name": theme_name})
    print(f"Set Theme '{theme_name}' Response:", response.status_code)
    print(response.json())

def test_run_effect():
    room = "Entrance"  # Assuming "Entrance" is a valid room
    effect_name = "Lightning"  # Assuming "Lightning" is a valid effect
    response = requests.post(f"{BASE_URL}/run_effect", json={"room": room, "effect_name": effect_name})
    print(f"Run Effect '{effect_name}' in '{room}' Response:", response.status_code)
    print(response.json())

def test_set_master_brightness():
    brightness = 0.8
    response = requests.post(f"{BASE_URL}/set_master_brightness", json={"brightness": brightness})
    print(f"Set Master Brightness to {brightness} Response:", response.status_code)
    print(response.json())

def test_trigger_lightning():
    response = requests.post(f"{BASE_URL}/trigger_lightning")
    print("Trigger Lightning Response:", response.status_code)
    print(response.json())

def test_run_channel_test():
    test_data = {
        "testType": "channel",
        "rooms": ["Entrance"],
        "channelValues": {
            "total_dimming": 255,
            "r_dimming": 255,
            "g_dimming": 0,
            "b_dimming": 0
        }
    }
    response = requests.post(f"{BASE_URL}/run_test", json=test_data)
    print("Run Channel Test Response:", response.status_code)
    print(response.json())

def test_run_effect_test():
    test_data = {
        "testType": "effect",
        "rooms": ["Entrance"],
        "effectName": "Lightning"
    }
    response = requests.post(f"{BASE_URL}/run_test", json=test_data)
    print("Run Effect Test Response:", response.status_code)
    print(response.json())

def test_stop_test():
    response = requests.post(f"{BASE_URL}/stop_test")
    print("Stop Test Response:", response.status_code)
    print(response.json())

if __name__ == "__main__":
    print("Starting API Tests")
    
    test_get_rooms()
    test_get_effects()
    test_get_themes()
    test_get_light_models()
    
    test_set_theme()
    time.sleep(2)  # Wait for theme to apply
    
    test_run_effect()
    time.sleep(5)  # Wait for effect to complete
    
    test_set_master_brightness()
    time.sleep(2)  # Wait for brightness change to apply
    
    test_trigger_lightning()
    time.sleep(5)  # Wait for lightning effect to complete
    
    test_run_channel_test()
    time.sleep(5)  # Wait for channel test to complete
    
    test_run_effect_test()
    time.sleep(5)  # Wait for effect test to complete
    
    test_stop_test()
    
    print("API Tests Completed")
