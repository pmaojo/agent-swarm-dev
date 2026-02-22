extends Node

# Main.gd
# Entry point for the Godot Visualizer.
# Connects to the Swarm Gateway to fetch game state.

var url_base = "http://localhost:18789"
var poll_timer: Timer

func _ready():
    print("Godot Visualizer Started")

    # Check if running on Web to determine API URL
    if OS.has_feature("web"):
        # On web, we are served from the same origin as the API, so relative path works
        url_base = ""
        print("Running in Web Mode")
    else:
        print("Running in Editor/Desktop Mode (defaulting to localhost:18789)")

    # Setup HTTP Request
    var http = HTTPRequest.new()
    http.name = "GameStateRequest"
    add_child(http)
    http.request_completed.connect(_on_request_completed)

    # Setup Polling Timer
    poll_timer = Timer.new()
    poll_timer.wait_time = 5.0
    poll_timer.autostart = true
    poll_timer.timeout.connect(func(): _fetch_game_state(http))
    add_child(poll_timer)

    # Initial Fetch
    _fetch_game_state(http)

func _fetch_game_state(http: HTTPRequest):
    var endpoint = url_base + "/api/v1/game-state"
    var err = http.request(endpoint)
    if err != OK:
        print("Error sending request: ", err)

func _on_request_completed(result, response_code, headers, body):
    if result != HTTPRequest.RESULT_SUCCESS:
        print("Request failed with result: ", result, " Code: ", response_code)
        return

    var json = JSON.new()
    var parse_err = json.parse(body.get_string_from_utf8())
    if parse_err != OK:
        print("JSON Parse Error: ", json.get_error_message())
        return

    var data = json.get_data()
    print("Game State Update: ", data)

    # TODO: Update 3D Scene based on data
    # _update_scene(data)
