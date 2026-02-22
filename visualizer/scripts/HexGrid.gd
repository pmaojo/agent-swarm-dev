extends Node3D

class_name HexGrid

# KayKit Assets
var _hex_grass_scene = preload("res://addons/kaykit_medieval_hexagon_pack/Assets/gltf/tiles/base/hex_grass.gltf")
var _cloud_scene = preload("res://addons/kaykit_medieval_hexagon_pack/Assets/gltf/decoration/nature/cloud_big.gltf")
var _agent_building_scene = preload("res://addons/kaykit_medieval_hexagon_pack/Assets/gltf/buildings/blue/building_tower_A_blue.gltf")

# Hex Dimensions
var hex_size : float = 1.0 # Radius to corner. KayKit hexes are usually ~1 unit radius.
var hex_width : float = sqrt(3) * hex_size
var hex_height : float = 2.0 * hex_size

# Keep track of spawned nodes so we can clear them on update
var spawned_nodes : Array[Node] = []

func _ready():
    pass

# Converts Axial Coordinates (q, r) to World Position (Vector3)
# Assumes a Pointy-Top orientation on the XZ plane
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
    
    # We will lay out the nodes in a spiral or a grid depending on the abstract graph.
    # Since the state_data might not have (q, r) coordinates, we'll auto-generate them
    # in a simple spiral pattern starting from (0,0) for visualization purposes.
    
    var nodes = []
    
    # Extract nodes if available in the parsed JSON
    if state_data.has("nodes"):
        nodes = state_data["nodes"]
    elif state_data.has("agents"): # fallback if the JSON is structured differently
        nodes = state_data["agents"]
    
    # Default to generating a 3x3 hex grid if there is no structure we can parse
    if nodes.is_empty():
        # Fake demo grid
        _generate_demo_grid(state_data)
        return
        
    # TODO: Once we have the real JSON structure from the python backend,
    # map nodes to specific (q, r) hexes using force-directed graph or spiral.
    _generate_demo_grid(state_data)


func _generate_demo_grid(state_data: Dictionary):
    # Generates a simple hexagonal field as a demo/placeholder
    var radius = 2
    for q in range(-radius, radius + 1):
        var r1 = max(-radius, -q - radius)
        var r2 = min(radius, -q + radius)
        for r in range(r1, r2 + 1):
            _spawn_hex(q, r, false, false)
            
    # Place a building at center
    _spawn_building(0, 0)
    
    # Place clouds as "fog of war" on the edges
    _spawn_cloud(3, 0)
    _spawn_cloud(-3, 0)
    _spawn_cloud(0, 3)

func _spawn_hex(q: int, r: int, has_fog: bool, has_agent: bool):
    var pos = axial_to_world(q, r)
    
    var tile = _hex_grass_scene.instantiate()
    tile.position = pos
    add_child(tile)
    spawned_nodes.append(tile)
    
func _spawn_cloud(q: int, r: int):
    var pos = axial_to_world(q, r)
    # Give it a bit of height
    pos.y = 1.0
    var cloud = _cloud_scene.instantiate()
    cloud.position = pos
    add_child(cloud)
    spawned_nodes.append(cloud)

func _spawn_building(q: int, r: int):
    var pos = axial_to_world(q, r)
    pos.y = 0.5 # Place slightly above base
    var bldg = _agent_building_scene.instantiate()
    bldg.position = pos
    add_child(bldg)
    spawned_nodes.append(bldg)
