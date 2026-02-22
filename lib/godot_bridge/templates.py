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

BRIDGE_GD = """
extends Node

# --- Citadel Bridge ---
# Handles WebSocket connection to Swarm Synapse.

signal game_state_updated(state)
signal mission_assigned(mission)
signal hardening_event(event)

var _ws = WebSocketClient.new()
var _url = "ws://localhost:18789/ws"

func _ready():
    _ws.connect("connection_established", self, "_on_connection_established")
    _ws.connect("connection_closed", self, "_on_connection_closed")
    _ws.connect("connection_error", self, "_on_connection_error")
    _ws.connect("data_received", self, "_on_data_received")

    print("Connecting to Citadel Bridge at: " + _url)
    var err = _ws.connect_to_url(_url)
    if err != OK:
        print("Unable to connect")
        set_process(false)

func _process(delta):
    _ws.poll()

func _on_connection_established(protocol):
    print("Connected to Citadel Bridge!")
    _ws.get_peer(1).put_packet(to_json({"method": "connect"}).to_utf8())

func _on_connection_closed(was_clean_close):
    print("Connection closed", was_clean_close)
    set_process(false)

func _on_connection_error():
    print("Connection error")
    set_process(false)

func _on_data_received():
    var packet = _ws.get_peer(1).get_packet().get_string_from_utf8()
    var data = parse_json(packet)

    if data.has("type"):
        match data.type:
            "game_state_update":
                emit_signal("game_state_updated", data.payload)
            "mission_assigned":
                emit_signal("mission_assigned", data.payload)
            "HARDENING_EVENT":
                emit_signal("hardening_event", data.payload)
            "hello-ok":
                print("Handshake successful. Agents: ", data.agents)
"""

CITADEL_MANAGER_GD = """
extends Node

# --- Citadel Manager ---
# Manages the 3D City-State of Repositories and Agents.
# Note: In Godot 3.x, use Spatial; in 4.x use Node3D. Assuming 3.x based on syntax like 'onready'.

# Preload scenes (mocked paths)
# const BuildingScene = preload("res://scenes/Building.tscn")
# const AgentScene = preload("res://scenes/Agent.tscn")

var buildings = {} # repo_id -> BuildingInstance
var agents = {} # agent_id -> AgentInstance

# onready var bridge = $Bridge

func _ready():
    var bridge = get_node("Bridge")
    if bridge:
        bridge.connect("game_state_updated", self, "_on_game_state_updated")
        bridge.connect("mission_assigned", self, "_on_mission_assigned")

func _on_game_state_updated(state):
    _update_buildings(state.get("repositories", []))
    _update_agents(state.get("party", []))

func _update_buildings(repos):
    for repo in repos:
        var repo_id = repo.get("id")
        if not buildings.has(repo_id):
            _spawn_building(repo)
        else:
            buildings[repo_id].update_state(repo)

func _spawn_building(repo):
    # var b = BuildingScene.instance()
    # add_child(b)

    # Position logic (simple grid for now)
    var idx = buildings.size()
    var x = (idx % 5) * 20
    var z = (idx / 5) * 20
    # b.translation = Vector3(x, 0, z)

    # b.init(repo)
    # buildings[repo.get("id")] = b
    pass

func _update_agents(party_data):
    for member in party_data:
        var agent_id = member.get("id")
        if not agents.has(agent_id):
            _spawn_agent(member)
        else:
            agents[agent_id].update_state(member)

func _spawn_agent(data):
    # var a = AgentScene.instance()
    # add_child(a)
    # a.init(data)
    # Default spawn near the Factory (0,0,0)
    # a.translation = Vector3(0, 0, 0)
    # agents[data.get("id")] = a
    pass

func _on_mission_assigned(mission):
    print("Mission assigned: ", mission)
    var agent_id = mission.get("agent_id")
    var repo_id = mission.get("repo_id")

    if agents.has(agent_id) and buildings.has(repo_id):
        var target_pos = buildings[repo_id].translation
        # agents[agent_id].move_to(target_pos)
        # agents[agent_id].set_task(mission.get("task"))
        pass
"""

BUILDING_GD = """
extends Spatial

# --- Building (Repository) ---
# Visual representation of a repository.

var repo_id: String
var repo_name: String
var tasks_pending: int = 0

# onready var label = $Label3D
# onready var scaffolding = $Scaffolding
# onready var mesh = $MeshInstance

func init(data):
    repo_id = data.get("id")
    repo_name = data.get("name")
    update_state(data)

func update_state(data):
    tasks_pending = data.get("tasks_pending", 0)
    # label.text = repo_name + "\n" + str(tasks_pending) + " Tasks"

    if tasks_pending > 0:
        # scaffolding.visible = true
        pass
    else:
        # scaffolding.visible = false
        pass

    if data.get("status") == "error":
        # mesh.material_override = load("res://materials/error_mat.tres")
        pass
    else:
        # mesh.material_override = load("res://materials/default_mat.tres")
        pass
"""
