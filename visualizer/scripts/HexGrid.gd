extends Node3D

class_name HexGrid

signal knowledge_node_selected(node_id: String, metadata: Dictionary)

var _hex_grass_scene: PackedScene = preload("res://addons/kaykit_medieval_hexagon_pack/Assets/gltf/tiles/base/hex_grass.gltf")

const BUILDING_ASSET_TEMPLATES: Dictionary = {
	"blue": "res://addons/kaykit_medieval_hexagon_pack/Assets/gltf/buildings/blue/building_castle_blue.gltf",
	"red": "res://addons/kaykit_medieval_hexagon_pack/Assets/gltf/buildings/red/building_castle_red.gltf",
	"green": "res://addons/kaykit_medieval_hexagon_pack/Assets/gltf/buildings/green/building_castle_green.gltf",
	"yellow": "res://addons/kaykit_medieval_hexagon_pack/Assets/gltf/buildings/yellow/building_castle_yellow.gltf",
	"neutral": "res://addons/kaykit_medieval_hexagon_pack/Assets/gltf/buildings/neutral/building_tower_A_neutral.gltf"
}

const SERVICE_HEALTH_COLORS: Dictionary = {
	"healthy": Color(0.35, 0.95, 0.45),
	"degraded": Color(0.95, 0.85, 0.25),
	"halted": Color(0.65, 0.65, 0.65),
	"under_attack": Color(1.0, 0.25, 0.25)
}

const COUNTRY_COLORS: Dictionary = {
	"The Swarm Motherland": "blue",
	"The Core Empire": "red",
	"The Front-End Republic": "green",
	"The Security Kingdom": "yellow"
}

const DEFAULT_COUNTRY_CENTERS: Array[Vector2i] = [
	Vector2i(0, 0),
	Vector2i(3, -1),
	Vector2i(-3, 1),
	Vector2i(0, 3)
]

const SERVICE_OFFSETS: Array[Vector2i] = [
	Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 1),
	Vector2i(-1, 0), Vector2i(0, -1), Vector2i(1, -1)
]

var hex_size: float = 1.0

var _base_grid_ready: bool = false
var _country_nodes: Dictionary = {}
var _service_nodes: Dictionary = {}
var _country_positions: Dictionary = {}
var _knowledge_nodes: Dictionary = {}
var _bug_nodes: Dictionary = {}
var _selected_knowledge_node_id: String = ""

func _ready() -> void:
	if not _base_grid_ready:
		_generate_base_grid(3)
		_base_grid_ready = true
	set_process(true)

func _process(delta: float) -> void:
	for bug_id in _bug_nodes.keys():
		var bug: Dictionary = _bug_nodes[bug_id]
		var node: Node3D = bug.get("node")
		var target: Vector3 = bug.get("target", node.position)
		if is_instance_valid(node):
			node.position = node.position.move_toward(target, delta * 1.75)

func axial_to_world(q: int, r: int) -> Vector3:
	var x: float = hex_size * sqrt(3.0) * (q + r / 2.0)
	var z: float = hex_size * 3.0 / 2.0 * r
	return Vector3(x, 0.0, z)

func update_grid(state_data: Dictionary) -> void:
	var countries: Array = state_data.get("countries", [])
	_update_country_positions(countries)
	_sync_countries(countries)
	var knowledge_tree: Array = state_data.get("knowledge_tree", [])
	_sync_knowledge_tree(knowledge_tree)

func _update_country_positions(countries: Array) -> void:
	for i in range(countries.size()):
		var country: Dictionary = countries[i]
		var country_id: String = str(country.get("id", "country-%d" % i))
		if not _country_positions.has(country_id):
			_country_positions[country_id] = DEFAULT_COUNTRY_CENTERS[i % DEFAULT_COUNTRY_CENTERS.size()]

func _sync_countries(countries: Array) -> void:
	var active_country_ids: Dictionary = {}

	for country in countries:
		var country_dict: Dictionary = country
		var country_id: String = str(country_dict.get("id", ""))
		if country_id.is_empty():
			continue

		active_country_ids[country_id] = true
		var country_name: String = str(country_dict.get("name", country_id))
		var center: Vector2i = _country_positions.get(country_id, Vector2i.ZERO)
		_sync_country_node(country_id, country_name, center)
		_sync_services(country_id, country_name, center, country_dict.get("services", []))

	for tracked_country_id in _country_nodes.keys():
		if not active_country_ids.has(tracked_country_id):
			_remove_country(tracked_country_id)

func _sync_country_node(country_id: String, country_name: String, center: Vector2i) -> void:
	var bucket: Dictionary = _country_nodes.get(country_id, {})
	if bucket.is_empty():
		var color_key: String = str(COUNTRY_COLORS.get(country_name, "neutral"))
		var scene_path: String = str(BUILDING_ASSET_TEMPLATES.get(color_key, BUILDING_ASSET_TEMPLATES["neutral"]))
		var model: Node3D = load(scene_path).instantiate()
		model.position = axial_to_world(center.x, center.y) + Vector3(0.0, 0.5, 0.0)
		add_child(model)
		var label: Label3D = _build_label(country_name, Color.AQUA, 48)
		label.position = model.position + Vector3(0.0, 2.5, 0.0)
		add_child(label)
		_country_nodes[country_id] = {"model": model, "label": label}
		return

	var existing_label: Label3D = bucket.get("label")
	if is_instance_valid(existing_label):
		existing_label.text = country_name

func _sync_services(country_id: String, country_name: String, center: Vector2i, services: Array) -> void:
	var active_service_ids: Dictionary = {}
	for i in range(services.size()):
		var service: Dictionary = services[i]
		var service_id: String = str(service.get("id", ""))
		if service_id.is_empty():
			continue
		active_service_ids[service_id] = true

		var offset: Vector2i = SERVICE_OFFSETS[i % SERVICE_OFFSETS.size()]
		var q: int = center.x + offset.x
		var r: int = center.y + offset.y
		var name: String = str(service.get("name", service_id))
		var health: String = str(service.get("health", "healthy"))
		_sync_service_node(country_id, country_name, service_id, name, health, int(service.get("hp", 100)), q, r)

	var stale_ids: Array[String] = []
	for tracked_id in _service_nodes.keys():
		if tracked_id.begins_with(country_id + "::"):
			var service_local_id: String = tracked_id.trim_prefix(country_id + "::")
			if not active_service_ids.has(service_local_id):
				stale_ids.append(tracked_id)

	for stale_id in stale_ids:
		_remove_service(stale_id)

func _sync_service_node(country_id: String, country_name: String, service_id: String, service_name: String, health: String, hp: int, q: int, r: int) -> void:
	var key: String = _service_key(country_id, service_id)
	var bucket: Dictionary = _service_nodes.get(key, {})
	var color_key: String = str(COUNTRY_COLORS.get(country_name, "neutral"))
	var scene_path: String = str(BUILDING_ASSET_TEMPLATES.get(color_key, BUILDING_ASSET_TEMPLATES["neutral"]))
	var status_color: Color = SERVICE_HEALTH_COLORS.get(health, SERVICE_HEALTH_COLORS["healthy"])
	var pos: Vector3 = axial_to_world(q, r) + Vector3(0.0, 0.5, 0.0)

	if bucket.is_empty():
		var model: Node3D = load(scene_path).instantiate()
		model.position = pos
		model.scale = Vector3(0.5, 0.5, 0.5)
		_set_mesh_modulate(model, status_color)
		add_child(model)

		var label: Label3D = _build_label(_service_label(service_name, health, hp), status_color, 28)
		label.position = pos + Vector3(0.0, 1.4, 0.0)
		add_child(label)
		_service_nodes[key] = {"model": model, "label": label}
		return

	var existing_model: Node3D = bucket.get("model")
	if is_instance_valid(existing_model):
		existing_model.position = pos
		_set_mesh_modulate(existing_model, status_color)
	var existing_label: Label3D = bucket.get("label")
	if is_instance_valid(existing_label):
		existing_label.position = pos + Vector3(0.0, 1.4, 0.0)
		existing_label.text = _service_label(service_name, health, hp)
		existing_label.modulate = status_color

func _set_mesh_modulate(node: Node, color: Color) -> void:
	if node is GeometryInstance3D:
		(node as GeometryInstance3D).modulate = color
	for child in node.get_children():
		_set_mesh_modulate(child, color)

func _service_key(country_id: String, service_id: String) -> String:
	return country_id + "::" + service_id

func _service_label(name: String, health: String, hp: int = 100) -> String:
	return "%s\n[%s] HP:%d" % [name, health, hp]

func _remove_country(country_id: String) -> void:
	var bucket: Dictionary = _country_nodes.get(country_id, {})
	if not bucket.is_empty():
		var model: Node = bucket.get("model")
		if is_instance_valid(model):
			model.queue_free()
		var label: Node = bucket.get("label")
		if is_instance_valid(label):
			label.queue_free()
		_country_nodes.erase(country_id)

	var prefix: String = country_id + "::"
	var stale_service_keys: Array[String] = []
	for service_key in _service_nodes.keys():
		if service_key.begins_with(prefix):
			stale_service_keys.append(service_key)
	for key in stale_service_keys:
		_remove_service(key)

func _remove_service(service_key: String) -> void:
	var bucket: Dictionary = _service_nodes.get(service_key, {})
	if bucket.is_empty():
		return
	var model: Node = bucket.get("model")
	if is_instance_valid(model):
		model.queue_free()
	var label: Node = bucket.get("label")
	if is_instance_valid(label):
		label.queue_free()
	_service_nodes.erase(service_key)

func _generate_base_grid(radius: int) -> void:
	for q in range(-radius - 2, radius + 3):
		var r1: int = max(-radius - 2, -q - (radius + 2))
		var r2: int = min(radius + 2, -q + (radius + 2))
		for r in range(r1, r2 + 1):
			_spawn_hex(q, r)

func _spawn_hex(q: int, r: int) -> void:
	var tile: Node3D = _hex_grass_scene.instantiate()
	tile.position = axial_to_world(q, r)
	add_child(tile)

func _build_label(text_value: String, color: Color, size: int) -> Label3D:
	var label := Label3D.new()
	label.text = text_value
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.outline_render_priority = 10
	label.modulate = color
	label.font_size = size
	return label

func _sync_knowledge_tree(knowledge_tree: Array) -> void:
	var active_ids: Dictionary = {}
	for i in range(knowledge_tree.size()):
		var node_data: Dictionary = knowledge_tree[i]
		var node_id: String = str(node_data.get("id", ""))
		if node_id.is_empty():
			continue
		active_ids[node_id] = true

		var q: int = -4 + int(i % 4)
		var r: int = 4 + int(i / 4)
		var unlocked: bool = bool(node_data.get("unlocked", false))
		var status_color: Color = Color(0.35, 0.95, 0.45) if unlocked else Color(0.95, 0.55, 0.25)
		var name: String = str(node_data.get("name", node_id))
		var prereqs: PackedStringArray = PackedStringArray(node_data.get("prerequisites", []))
		var cost: Dictionary = node_data.get("cost", {})
		var budget: String = str(cost.get("budget", "0"))
		var time_cost: String = str(cost.get("time_hours", "0"))
		var label_text: String = "%s\nprereq:%s\n$%s / %sh" % [name, ",".join(prereqs), budget, time_cost]

		var bucket: Dictionary = _knowledge_nodes.get(node_id, {})
		var pos: Vector3 = axial_to_world(q, r) + Vector3(0.0, 1.8, 0.0)
		if bucket.is_empty():
			var root := Node3D.new()
			root.position = pos
			add_child(root)
			var marker := MeshInstance3D.new()
			marker.mesh = SphereMesh.new()
			marker.scale = Vector3(0.2, 0.2, 0.2)
			marker.modulate = status_color
			root.add_child(marker)
			var area := Area3D.new()
			var shape := CollisionShape3D.new()
			var sphere := SphereShape3D.new()
			sphere.radius = 0.4
			shape.shape = sphere
			area.add_child(shape)
			area.input_ray_pickable = true
			area.input_event.connect(_on_knowledge_area_input.bind(node_id))
			root.add_child(area)
			var label: Label3D = _build_label(label_text, status_color, 18)
			label.position = Vector3(0.0, 0.7, 0.0)
			root.add_child(label)
			_knowledge_nodes[node_id] = {
				"root": root,
				"marker": marker,
				"label": label,
				"metadata": node_data.duplicate(true)
			}
		else:
			var root_node: Node3D = bucket.get("root")
			if is_instance_valid(root_node):
				root_node.position = pos
			var existing_label: Label3D = bucket.get("label")
			if is_instance_valid(existing_label):
				existing_label.text = label_text
				existing_label.modulate = status_color
			var existing_marker: MeshInstance3D = bucket.get("marker")
			if is_instance_valid(existing_marker):
				existing_marker.modulate = status_color
			bucket["metadata"] = node_data.duplicate(true)
			_knowledge_nodes[node_id] = bucket

		if node_id == _selected_knowledge_node_id:
			_apply_knowledge_selection_style(node_id, true)

	var stale_ids: Array[String] = []
	for tracked_id in _knowledge_nodes.keys():
		if not active_ids.has(tracked_id):
			stale_ids.append(tracked_id)
	for stale_id in stale_ids:
		var bucket: Dictionary = _knowledge_nodes.get(stale_id, {})
		if not bucket.is_empty():
			var root_node: Node = bucket.get("root")
			if is_instance_valid(root_node):
				root_node.queue_free()
		_knowledge_nodes.erase(stale_id)
		if stale_id == _selected_knowledge_node_id:
			_selected_knowledge_node_id = ""

func _on_knowledge_area_input(_camera: Node, event: InputEvent, _event_position: Vector3, _event_normal: Vector3, _shape_idx: int, node_id: String) -> void:
	if event is InputEventMouseButton:
		var mouse_event: InputEventMouseButton = event
		if mouse_event.button_index == MOUSE_BUTTON_LEFT and mouse_event.pressed:
			_select_knowledge_node(node_id)

func _select_knowledge_node(node_id: String) -> void:
	if _selected_knowledge_node_id == node_id:
		return
	if not _selected_knowledge_node_id.is_empty():
		_apply_knowledge_selection_style(_selected_knowledge_node_id, false)
	_selected_knowledge_node_id = node_id
	_apply_knowledge_selection_style(node_id, true)
	var bucket: Dictionary = _knowledge_nodes.get(node_id, {})
	if bucket.is_empty():
		return
	var metadata: Dictionary = bucket.get("metadata", {}).duplicate(true)
	knowledge_node_selected.emit(node_id, metadata)

func _apply_knowledge_selection_style(node_id: String, selected: bool) -> void:
	var bucket: Dictionary = _knowledge_nodes.get(node_id, {})
	if bucket.is_empty():
		return
	var label: Label3D = bucket.get("label")
	if is_instance_valid(label):
		label.outline_render_priority = 20 if selected else 10
	var marker: MeshInstance3D = bucket.get("marker")
	if is_instance_valid(marker):
		marker.scale = Vector3(0.3, 0.3, 0.3) if selected else Vector3(0.2, 0.2, 0.2)


func apply_combat_event(event_data: Dictionary) -> void:
	var event_type: String = str(event_data.get("type", ""))
	if event_type == "keepalive":
		return
	var payload: Dictionary = event_data.get("payload", {})
	if event_type == "BUG_SPAWNED":
		_spawn_bug(payload)
	elif event_type == "SERVICE_DAMAGED":
		_spawn_bug(payload)
	elif event_type == "SERVICE_RECOVERED":
		_despawn_bug_for_service(str(payload.get("service_id", "")))

func _spawn_bug(payload: Dictionary) -> void:
	var service_id: String = str(payload.get("details", {}).get("service_id", payload.get("service_id", "")))
	if service_id.is_empty():
		service_id = "unknown"
	var bug_id: String = "bug-" + service_id + "-" + str(Time.get_ticks_msec())
	var marker := MeshInstance3D.new()
	marker.mesh = SphereMesh.new()
	marker.scale = Vector3(0.2, 0.2, 0.2)
	marker.modulate = Color(0.9, 0.1, 0.1)
	marker.position = axial_to_world(-5 + randi() % 3, 5 - randi() % 3) + Vector3(0, 0.8, 0)
	add_child(marker)

	var target: Vector3 = _find_service_target(service_id)
	_bug_nodes[bug_id] = {"node": marker, "target": target, "service_id": service_id}

func _find_service_target(service_id: String) -> Vector3:
	for key in _service_nodes.keys():
		if key.ends_with("::" + service_id):
			var bucket: Dictionary = _service_nodes[key]
			var model: Node3D = bucket.get("model")
			if is_instance_valid(model):
				return model.position + Vector3(0, 0.8, 0)
	for key in _service_nodes.keys():
		var bucket: Dictionary = _service_nodes[key]
		var model: Node3D = bucket.get("model")
		if is_instance_valid(model):
			return model.position + Vector3(0, 0.8, 0)
	return axial_to_world(0, 0) + Vector3(0, 0.8, 0)

func _despawn_bug_for_service(service_id: String) -> void:
	var stale: Array[String] = []
	for bug_id in _bug_nodes.keys():
		var bug: Dictionary = _bug_nodes[bug_id]
		if str(bug.get("service_id", "")) == service_id:
			var node: Node = bug.get("node")
			if is_instance_valid(node):
				node.queue_free()
			stale.append(bug_id)
	for bug_id in stale:
		_bug_nodes.erase(bug_id)
