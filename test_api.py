import requests
import json
import time

BASE_URL = "http://192.168.1.238:5000/api"

def run_test(test_func):
    try:
        result = test_func()
        print(f"{test_func.__name__} - Success")
        return True
    except AssertionError as e:
        print(f"{test_func.__name__} - Failed: {str(e)}")
        return False
    except Exception as e:
        print(f"{test_func.__name__} - Error: {str(e)}")
        return False

def test_get_rooms():
    response = requests.get(f"{BASE_URL}/rooms")
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    rooms = response.json()
    assert isinstance(rooms, dict), "Expected rooms to be a dictionary"
    assert len(rooms) > 0, "Expected at least one room"
    print("Get Rooms Response:", response.status_code)
    print(json.dumps(rooms, indent=2))

def test_get_effects():
    response = requests.get(f"{BASE_URL}/effects")
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    effects = response.json()
    assert isinstance(effects, dict), "Expected effects to be a dictionary"
    assert len(effects) > 0, "Expected at least one effect"
    print("Get Effects Response:", response.status_code)
    print(json.dumps(effects, indent=2))

def test_get_themes():
    response = requests.get(f"{BASE_URL}/themes")
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    themes = response.json()
    assert isinstance(themes, dict), "Expected themes to be a dictionary"
    assert len(themes) > 0, "Expected at least one theme"
    print("Get Themes Response:", response.status_code)
    print(json.dumps(themes, indent=2))

def test_get_light_models():
    response = requests.get(f"{BASE_URL}/light_models")
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    light_models = response.json()
    assert isinstance(light_models, dict), "Expected light models to be a dictionary"
    assert len(light_models) > 0, "Expected at least one light model"
    print("Get Light Models Response:", response.status_code)
    print(json.dumps(light_models, indent=2))

def test_set_theme():
    theme_name = "Ocean"  # Assuming "Ocean" is a valid theme
    response = requests.post(f"{BASE_URL}/set_theme", json={"theme_name": theme_name})
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    result = response.json()
    assert result["status"] == "success", f"Expected status 'success', got {result['status']}"
    print(f"Set Theme '{theme_name}' Response:", response.status_code)
    print(result)

def test_run_effect():
    room = "Entrance"  # Assuming "Entrance" is a valid room
    effect_name = "Lightning"  # Assuming "Lightning" is a valid effect
    response = requests.post(f"{BASE_URL}/run_effect", json={"room": room, "effect_name": effect_name})
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    result = response.json()
    assert result["status"] == "success", f"Expected status 'success', got {result['status']}"
    print(f"Run Effect '{effect_name}' in '{room}' Response:", response.status_code)
    print(result)

def test_set_master_brightness():
    brightness = 0.8
    response = requests.post(f"{BASE_URL}/set_master_brightness", json={"brightness": brightness})
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    result = response.json()
    assert result["status"] == "success", f"Expected status 'success', got {result['status']}"
    assert result["master_brightness"] == brightness, f"Expected brightness {brightness}, got {result['master_brightness']}"
    print(f"Set Master Brightness to {brightness} Response:", response.status_code)
    print(result)

def test_trigger_lightning():
    response = requests.post(f"{BASE_URL}/trigger_lightning")
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    result = response.json()
    assert "message" in result, "Expected 'message' in response"
    print("Trigger Lightning Response:", response.status_code)
    print(result)

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
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    result = response.json()
    assert "message" in result, "Expected 'message' in response"
    print("Run Channel Test Response:", response.status_code)
    print(result)

def test_run_effect_test():
    test_data = {
        "testType": "effect",
        "rooms": ["Entrance"],
        "effectName": "Lightning"
    }
    response = requests.post(f"{BASE_URL}/run_test", json=test_data)
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    result = response.json()
    assert "message" in result, "Expected 'message' in response"
    print("Run Effect Test Response:", response.status_code)
    print(result)

def test_stop_test():
    response = requests.post(f"{BASE_URL}/stop_test")
    assert response.status_code == 200, f"Expected status code 200, got {response.status_code}"
    result = response.json()
    assert "message" in result, "Expected 'message' in response"
    print("Stop Test Response:", response.status_code)
    print(result)

if __name__ == "__main__":
    print("Starting API Tests")
    
    test_results = []
    test_results.append(run_test(test_get_rooms))
    test_results.append(run_test(test_get_effects))
    test_results.append(run_test(test_get_themes))
    test_results.append(run_test(test_get_light_models))
    
    test_results.append(run_test(test_set_theme))
    time.sleep(2)  # Wait for theme to apply
    
    test_results.append(run_test(test_run_effect))
    time.sleep(5)  # Wait for effect to complete
    
    test_results.append(run_test(test_set_master_brightness))
    time.sleep(2)  # Wait for brightness change to apply
    
    test_results.append(run_test(test_trigger_lightning))
    time.sleep(5)  # Wait for lightning effect to complete
    
    test_results.append(run_test(test_run_channel_test))
    time.sleep(5)  # Wait for channel test to complete
    
    test_results.append(run_test(test_run_effect_test))
    time.sleep(5)  # Wait for effect test to complete
    
    test_results.append(run_test(test_stop_test))
    
    print("\nAPI Tests Completed")
    print(f"Total tests: {len(test_results)}")
    print(f"Successful tests: {test_results.count(True)}")
    print(f"Failed tests: {test_results.count(False)}")
