extends Node

# Main.gd
# Entry point for the Godot Visualizer.
# Connects to the Swarm Gateway to fetch game state and renders strategy-game style HUD.

const COMMAND_ASSIGN_MISSION: String = "ASSIGN_MISSION"
const COMMAND_PAUSE_AGENT: String = "PAUSE_AGENT"
const COMMAND_RESUME_AGENT: String = "RESUME_AGENT"
const COMMAND_PATCH_SERVICE: String = "PATCH_SERVICE"
const COMMAND_ROLLBACK_SERVICE: String = "ROLLBACK_SERVICE"
const COMMAND_RESTART_SERVICE: String = "RESTART_SERVICE"
const COMMAND_ISOLATE_SERVICE: String = "ISOLATE_SERVICE"

var url_base: String = "http://localhost:18789"
var poll_timer: Timer
var _last_game_state_snapshot: String = ""
var _last_game_state: Dictionary = {}
var _combat_socket: WebSocketPeer = WebSocketPeer.new()

func _ready() -> void:
	print("Godot Visualizer Started")

	if OS.has_feature("web"):
		url_base = ""
		print("Running in Web Mode")
	else:
		print("Running in Editor/Desktop Mode (defaulting to localhost:18789)")

	var state_http := HTTPRequest.new()
	state_http.name = "GameStateRequest"
	add_child(state_http)
	state_http.request_completed.connect(_on_state_request_completed)

	var command_http := HTTPRequest.new()
	command_http.name = "ControlCommandRequest"
	add_child(command_http)
	command_http.request_completed.connect(_on_command_request_completed)

	poll_timer = Timer.new()
	poll_timer.wait_time = 5.0
	poll_timer.autostart = true
	poll_timer.timeout.connect(func() -> void: _fetch_game_state(state_http))
	add_child(poll_timer)

	_bind_controls()
	_connect_combat_stream()
	set_process(true)
	_fetch_game_state(state_http)


func _process(delta: float) -> void:
	_poll_combat_stream()

func _connect_combat_stream() -> void:
	var ws_url: String = "ws://localhost:18789/api/v1/events/combat/stream"
	if OS.has_feature("web"):
		ws_url = "ws://" + JavaScriptBridge.eval("window.location.host") + "/api/v1/events/combat/stream"
	var err: int = _combat_socket.connect_to_url(ws_url)
	if err != OK:
		print("Unable to connect combat stream: ", err)

func _poll_combat_stream() -> void:
	if _combat_socket.get_ready_state() == WebSocketPeer.STATE_CONNECTING:
		_combat_socket.poll()
		return
	if _combat_socket.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return
	_combat_socket.poll()
	while _combat_socket.get_available_packet_count() > 0:
		var packet: PackedByteArray = _combat_socket.get_packet()
		var text: String = packet.get_string_from_utf8()
		var parser := JSON.new()
		if parser.parse(text) == OK:
			var event_data: Dictionary = parser.get_data()
			if get_node_or_null("HexGridManager"):
				$HexGridManager.apply_combat_event(event_data)

func _bind_controls() -> void:
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/DispatchQuestButton"):
		$CanvasLayer/HUD/Margin/VBox/Actions/DispatchQuestButton.pressed.connect(func() -> void:
			_send_control_command(COMMAND_ASSIGN_MISSION, "agent-coder", "repo-root", "Stabilize service mesh")
		)
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/PauseButton"):
		$CanvasLayer/HUD/Margin/VBox/Actions/PauseButton.pressed.connect(func() -> void:
			_send_control_command(COMMAND_PAUSE_AGENT, "agent-coder", "repo-root", "Hold position")
		)
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/ResumeButton"):
		$CanvasLayer/HUD/Margin/VBox/Actions/ResumeButton.pressed.connect(func() -> void:
			_send_control_command(COMMAND_RESUME_AGENT, "agent-coder", "repo-root", "Rejoin formation")
		)
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/PatchButton"):
		$CanvasLayer/HUD/Margin/VBox/Actions/PatchButton.pressed.connect(func() -> void:
			_send_control_command(COMMAND_PATCH_SERVICE, "agent-coder", "service-gateway", "Apply hot patch")
		)
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/RollbackButton"):
		$CanvasLayer/HUD/Margin/VBox/Actions/RollbackButton.pressed.connect(func() -> void:
			_send_control_command(COMMAND_ROLLBACK_SERVICE, "agent-reviewer", "service-web", "Rollback unstable release")
		)
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/RestartButton"):
		$CanvasLayer/HUD/Margin/VBox/Actions/RestartButton.pressed.connect(func() -> void:
			_send_control_command(COMMAND_RESTART_SERVICE, "agent-deployer", "service-orchestrator", "Controlled restart")
		)
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/IsolateButton"):
		$CanvasLayer/HUD/Margin/VBox/Actions/IsolateButton.pressed.connect(func() -> void:
			_send_control_command(COMMAND_ISOLATE_SERVICE, "agent-architect", "service-guardian", "Isolate compromised node")
		)

func _fetch_game_state(http: HTTPRequest) -> void:
	var endpoint: String = url_base + "/api/v1/game-state"
	var err: int = http.request(endpoint)
	if err != OK:
		print("Error sending request: ", err)

func _on_state_request_completed(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS:
		print("Request failed with result: ", result, " Code: ", response_code)
		return

	var json := JSON.new()
	var parse_err: int = json.parse(body.get_string_from_utf8())
	if parse_err != OK:
		print("JSON Parse Error: ", json.get_error_message())
		return

	var data: Dictionary = json.get_data()
	var snapshot: String = JSON.stringify(data)
	if snapshot == _last_game_state_snapshot:
		return

	_last_game_state_snapshot = snapshot
	_last_game_state = data
	_update_hud(data)

	if get_node_or_null("CanvasLayer/TelemetryPanel/TelemetryMargin/RichTextLabel"):
		$CanvasLayer/TelemetryPanel/TelemetryMargin/RichTextLabel.text = JSON.stringify(data, "  ")

	if get_node_or_null("HexGridManager"):
		$HexGridManager.update_grid(data)

func _update_hud(data: Dictionary) -> void:
	var countries: Array = data.get("countries", [])
	var all_services: int = 0
	var degraded_services: int = 0
	var halted_services: int = 0
	var under_attack_services: int = 0

	for country_variant in countries:
		var country: Dictionary = country_variant
		var services: Array = country.get("services", [])
		all_services += services.size()
		for service_variant in services:
			var service: Dictionary = service_variant
			var health: String = str(service.get("health", "healthy"))
			match health:
				"degraded":
					degraded_services += 1
				"halted":
					halted_services += 1
				"under_attack":
					under_attack_services += 1

	if has_node("CanvasLayer/HUD/Margin/VBox/Title"):
		$CanvasLayer/HUD/Margin/VBox/Title.text = "⚔️ Trono de la Sinapsis — Guerra Multi-Swarm"
	if has_node("CanvasLayer/HUD/Margin/VBox/TurnBanner"):
		$CanvasLayer/HUD/Margin/VBox/TurnBanner.text = "Turno %s · Proyectos %d · Reinos %d" % [_turn_number(), data.get("repositories", []).size(), countries.size()]
	if has_node("CanvasLayer/HUD/Margin/VBox/Stats/ServicesLabel"):
		$CanvasLayer/HUD/Margin/VBox/Stats/ServicesLabel.text = "Servicios vigilados: %d" % all_services
	if has_node("CanvasLayer/HUD/Margin/VBox/Stats/ThreatLabel"):
		$CanvasLayer/HUD/Margin/VBox/Stats/ThreatLabel.text = "Amenazas: %d en asedio" % under_attack_services
	if has_node("CanvasLayer/HUD/Margin/VBox/Stats/DegradedLabel"):
		$CanvasLayer/HUD/Margin/VBox/Stats/DegradedLabel.text = "Degradados: %d · Detenidos: %d" % [degraded_services, halted_services]
	if has_node("CanvasLayer/HUD/Margin/VBox/OrderLog"):
		$CanvasLayer/HUD/Margin/VBox/OrderLog.text = _build_order_log(data)

func _turn_number() -> int:
	if _last_game_state.is_empty():
		return 1
	var spent: float = float(_last_game_state.get("daily_budget", {}).get("spent", 0.0))
	return int(spent * 10.0) + 1

func _build_order_log(data: Dictionary) -> String:
	var logs: Array[String] = []
	for country_variant in data.get("countries", []):
		var country: Dictionary = country_variant
		for service_variant in country.get("services", []):
			var service: Dictionary = service_variant
			var health: String = str(service.get("health", "healthy"))
			if health != "healthy":
				logs.append("• %s/%s => %s" % [country.get("name", "?"), service.get("name", "?"), health])
	if logs.is_empty():
		return "Consejo de Guerra: todas las líneas estables."
	return "\n".join(logs)

func _send_control_command(command_name: String, agent_id: String, repo_id: String, task: String) -> void:
	if not has_node("ControlCommandRequest"):
		return
	var endpoint: String = url_base + "/api/v1/control/commands"
	var payload: Dictionary = {
		"command": command_name,
		"agent_id": agent_id,
		"repo_id": repo_id,
		"task": task,
		"metadata": {
			"source": "godot-war-room",
			"turn": str(_turn_number())
		}
	}
	var headers: PackedStringArray = PackedStringArray(["Content-Type: application/json"])
	var body: String = JSON.stringify(payload)
	var err: int = $ControlCommandRequest.request(endpoint, headers, HTTPClient.METHOD_POST, body)
	if err != OK:
		print("Error sending control command: ", err)

func _on_command_request_completed(result: int, response_code: int, headers: PackedStringArray, body: PackedByteArray) -> void:
	var status_message: String = "Orden no confirmada"
	if result == HTTPRequest.RESULT_SUCCESS and response_code >= 200 and response_code < 300:
		status_message = "Orden despachada al Alto Mando"
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/CommandStatus"):
		$CanvasLayer/HUD/Margin/VBox/Actions/CommandStatus.text = status_message
