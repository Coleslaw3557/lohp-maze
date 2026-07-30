"""Room-local answer-pool names shared by the server and audio console."""


ROOM_ANSWER_POOL_PREFIXES = {
    "Vertical Moop March": "VerticalMoopMarch",
    "Bike Lock Room": "BikeLockRoom",
    "Camp Sign": "CampSign",
    "Cop Dodge": "CopDodge",
    "Cuddle Cross": "CuddleCross",
    "Deep Playa Handshake": "DeepPlayaHandshake",
    "Entrance": "Entrance",
    "Exit": "Exit",
    "Gate": "Gate",
    "Guy Line Climb": "GuyLineClimb",
    "Monkey Room": "MonkeyRoom",
    "No Friends Monday": "NoFriendsMonday",
    "Photo Bomb Room": "PhotoBombRoom",
    "Porto Room": "PortoRoom",
    "Sparkle Pony Room": "SparklePonyRoom",
    "Temple Room": "TempleRoom",
}

ANSWER_EFFECTS = {
    "CorrectAnswer": ("RightAnswer", "right answer"),
    "WrongAnswer": ("WrongAnswer", "wrong answer"),
}

ROOM_BACKGROUND_POOLS = {
    "Vertical Moop March": "VerticalMoopMarch-Background",
    "Bike Lock Room": "BikeLockRoom-Background",
    "Camp Sign": "CampSign-Background",
    "Cop Dodge": "CopDodge-Background",
    "Cuddle Cross": "Cuddle-Lava-Bed",
    "Deep Playa Handshake": "DeepPlaya-BG",
    "Entrance": "Entrance-Background",
    "Exit": "Exit-Background",
    "Gate": "Gate-Background",
    "Guy Line Climb": "GuyLineClimb-Background",
    "Monkey Room": "MonkeyRoom-Background",
    "No Friends Monday": "NoFriendsMonday-Background",
    "Photo Bomb Room": "PhotoBomb-BG",
    "Porto Room": "PortoStandBy",
    "Sparkle Pony Room": "SparklePonyRoom-Background",
    "Temple Room": "TempleRoom-Background",
}


def answer_pool_name(room, base_effect):
    """Return the room-local answer pool name for a shared answer effect."""
    suffix = ANSWER_EFFECTS.get(base_effect)
    prefix = ROOM_ANSWER_POOL_PREFIXES.get(room)
    if not suffix or not prefix:
        return None
    return f"{prefix}-{suffix[0]}"


def background_pool_name(room):
    """Return the room-local background/ambience pool name."""
    return ROOM_BACKGROUND_POOLS.get(room)
