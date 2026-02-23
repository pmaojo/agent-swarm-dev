extends Node3D

class_name HexGrid

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

func _ready() -> void:
	if not _base_grid_ready:
		_generate_base_grid(3)
		_base_grid_ready = true

func axial_to_world(q: int, r: int) -> Vector3:
	var x: float = hex_size * sqrt(3.0) * (q + r / 2.0)
	var z: float = hex_size * 3.0 / 2.0 * r
	return Vector3(x, 0.0, z)

func update_grid(state_data: Dictionary) -> void:
	var countries: Array = state_data.get("countries", [])
	_update_country_positions(countries)
	_sync_countries(countries)

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
		_sync_service_node(country_id, country_name, service_id, name, health, q, r)

	var stale_ids: Array[String] = []
	for tracked_id in _service_nodes.keys():
		if tracked_id.begins_with(country_id + "::"):
			var service_local_id: String = tracked_id.trim_prefix(country_id + "::")
			if not active_service_ids.has(service_local_id):
				stale_ids.append(tracked_id)

	for stale_id in stale_ids:
		_remove_service(stale_id)

func _sync_service_node(country_id: String, country_name: String, service_id: String, service_name: String, health: String, q: int, r: int) -> void:
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

		var label: Label3D = _build_label(_service_label(service_name, health), status_color, 28)
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
		existing_label.text = _service_label(service_name, health)
		existing_label.modulate = status_color

func _set_mesh_modulate(node: Node, color: Color) -> void:
	if node is GeometryInstance3D:
		(node as GeometryInstance3D).modulate = color
	for child in node.get_children():
		_set_mesh_modulate(child, color)

func _service_key(country_id: String, service_id: String) -> String:
	return country_id + "::" + service_id

func _service_label(name: String, health: String) -> String:
	return "%s\n[%s]" % [name, health]

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
