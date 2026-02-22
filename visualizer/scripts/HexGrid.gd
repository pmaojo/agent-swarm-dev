extends Node3D

class_name HexGrid

# KayKit Assets
var _hex_grass_scene = preload("res://addons/kaykit_medieval_hexagon_pack/Assets/gltf/tiles/base/hex_grass.gltf")
var _cloud_scene = preload("res://addons/kaykit_medieval_hexagon_pack/Assets/gltf/decoration/nature/cloud_big.gltf")
var _country_building_scene = preload("res://addons/kaykit_medieval_hexagon_pack/Assets/gltf/buildings/blue/building_tower_A_blue.gltf")
var _agent_token_scene = preload("res://addons/kaykit_medieval_hexagon_pack/Assets/gltf/decoration/props/tent.gltf")

# Hex Dimensions
var hex_size : float = 1.0 
var hex_width : float = sqrt(3) * hex_size
var hex_height : float = 2.0 * hex_size

# Keep track of spawned nodes so we can clear them on update
var spawned_nodes : Array[Node] = []

func _ready():
	pass

# Converts Axial Coordinates (q, r) to World Position (Vector3)
func axial_to_world(q: int, r: int) -> Vector3:
	var x = hex_size * sqrt(3.0) * (q + r / 2.0)
	var z = hex_size * 3.0 / 2.0 * r
	return Vector3(x, 0, z)

func clear_grid():
	for child in spawned_nodes:
		if is_instance_valid(child):
			child.queue_free()
	spawned_nodes.clear()

func update_grid(state_data: Dictionary):
	clear_grid()
	
	# 1. Background Hexes
	_generate_base_grid(3)

	# 2. Build Agent Lookup
	var agent_map = {}
	for agent in state_data.get("party", []):
		agent_map[agent.get("id", "")] = agent

	# 3. Map Repositories (Countries)
	var repos = state_data.get("repositories", [])
	var repo_centers = [
		Vector2i(0, 0),
		Vector2i(3, -1),
		Vector2i(-3, 1),
		Vector2i(0, 3)
	]

	for i in range(repos.size()):
		var repo = repos[i]
		var center = repo_centers[i % repo_centers.size()]
		_spawn_building(center.x, center.y, repo.get("name", "Unknown Territory"))
		
		# 4. Map Agents for this country
		var agents = repo.get("swarm", [])
		var agent_offsets = [
			Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 1),
			Vector2i(-1, 0), Vector2i(0, -1), Vector2i(1, -1)
		]
		
		for j in range(agents.size()):
			var agent_id = agents[j]
			var offset = agent_offsets[j % agent_offsets.size()]
			var agent_info = agent_map.get(agent_id, {})
			_spawn_agent(center.x + offset.x, center.y + offset.y, agent_info)

func _generate_base_grid(radius: int):
	for q in range(-radius - 2, radius + 3):
		var r1 = max(-radius - 2, -q - (radius + 2))
		var r2 = min(radius + 2, -q + (radius + 2))
		for r in range(r1, r2 + 1):
			_spawn_hex(q, r)

func _spawn_hex(q: int, r: int):
	var pos = axial_to_world(q, r)
	var tile = _hex_grass_scene.instantiate()
	tile.position = pos
	add_child(tile)
	spawned_nodes.append(tile)
	
func _spawn_building(q: int, r: int, label_text: String):
	var pos = axial_to_world(q, r)
	pos.y = 0.5
	var bldg = _country_building_scene.instantiate()
	bldg.position = pos
	add_child(bldg)
	spawned_nodes.append(bldg)
	
	_add_floating_text(pos + Vector3(0, 2, 0), label_text, Color.AQUA)

func _spawn_agent(q: int, r: int, agent_info: Dictionary):
	var pos = axial_to_world(q, r)
	pos.y = 0.5
	var token = _agent_token_scene.instantiate()
	token.position = pos
	token.scale = Vector3(0.5, 0.5, 0.5)
	add_child(token)
	spawned_nodes.append(token)
	
	var agent_id = agent_info.get("id", "Unknown")
	var status = agent_info.get("current_action", "Standby")
	var display_text = agent_id + "\n[" + status + "]"
	
	var color = Color.YELLOW
	if status != "Standby":
		color = Color.GREEN_YELLOW
		
	_add_floating_text(pos + Vector3(0, 1.2, 0), display_text, color)

func _add_floating_text(pos: Vector3, text: String, color: Color):
	var label = Label3D.new()
	label.text = text
	label.position = pos
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.outline_render_priority = 10
	label.modulate = color
	label.font_size = 48 # Slightly smaller for multiline
	add_child(label)
	spawned_nodes.append(label)
