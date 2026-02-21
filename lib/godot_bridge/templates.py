AGENT_UNIT_GD = """
extends CharacterBody2D

# --- Swarm Agent Unit ---
# Connects to Synapse WebSocket and visualizes Agent state.

export var agent_name: String = "Unknown"
export var role: String = "Villager"
export var hp: float = 100.0
export var max_hp: float = 100.0
export var resource: float = 0.0

# UI
onready var hp_bar = $HealthBar
onready var label = $NameLabel
onready var role_icon = $RoleIcon

func _ready():
    label.text = agent_name
    hp_bar.value = hp
    update_role_visuals()

func update_state(data: Dictionary):
    hp = data.get("stats", {}).get("hp", 100.0)
    resource = data.get("stats", {}).get("mana", 0.0)
    var status = data.get("current_action", "Idle")

    # Animate based on status
    if status == "working":
        $AnimationPlayer.play("Work")
    elif status == "thinking":
        $AnimationPlayer.play("Think")
    else:
        $AnimationPlayer.play("Idle")

    hp_bar.value = hp

func update_role_visuals():
    match role:
        "Warrior": # Coder
            role_icon.texture = load("res://assets/coder_sword.png")
        "Wizard": # Architect
            role_icon.texture = load("res://assets/architect_staff.png")
        "Bard": # PM
            role_icon.texture = load("res://assets/pm_lute.png")
        "Cleric": # Reviewer
            role_icon.texture = load("res://assets/reviewer_shield.png")
        _:
            role_icon.texture = load("res://assets/default_unit.png")
"""

FOG_MANAGER_GD = """
extends Node2D

# --- Fog of War Manager ---
# Reads Synapse Fog Map and updates visual mask.

var fog_texture: ImageTexture
var fog_image: Image
var grid_size: int = 64

func _ready():
    # Initialize Fog Texture (Black)
    fog_image = Image.new()
    fog_image.create(1024, 1024, false, Image.FORMAT_RGBA8)
    fog_image.fill(Color(0, 0, 0, 0.8)) # Semi-transparent black
    fog_texture = ImageTexture.new()
    fog_texture.create_from_image(fog_image)

    $Sprite.texture = fog_texture

func update_fog(fog_map: Dictionary):
    fog_image.lock()
    for node_id in fog_map.keys():
        var state = fog_map[node_id]
        if state == "visible":
            # Determine position (mocked here, needs graph layout)
            var pos = get_node_position(node_id)
            reveal_area(pos)
    fog_image.unlock()
    fog_texture.set_data(fog_image)

func reveal_area(pos: Vector2):
    # Clear circle around position
    var radius = 2
    for x in range(pos.x - radius, pos.x + radius):
        for y in range(pos.y - radius, pos.y + radius):
            fog_image.set_pixel(x, y, Color(0, 0, 0, 0)) # Transparent

func get_node_position(id: String) -> Vector2:
    # Hash ID to coordinate? Or use Layout service?
    # For MVP, hash to grid.
    var h = id.hash()
    return Vector2(h % 1024, (h / 1024) % 1024)
"""
