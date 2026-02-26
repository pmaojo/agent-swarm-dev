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
var _characters: Array = []
var _selected_character_id: String = ""
var _selected_agent_id: String = "agent-coder"
var _selected_knowledge_node_id: String = ""
var _selected_knowledge_metadata: Dictionary = {}
var _is_user_editing_loadout: bool = false
var _is_programmatic_loadout_update: bool = false
var _character_lab_initialized: bool = false
var _character_lab_last_rendered_character_id: String = ""
var _character_lab_should_rehydrate_after_save: bool = false

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

	var characters_http := HTTPRequest.new()
	characters_http.name = "CharactersRequest"
	add_child(characters_http)
	characters_http.request_completed.connect(_on_characters_request_completed)

	var character_select_http := HTTPRequest.new()
	character_select_http.name = "CharacterSelectRequest"
	add_child(character_select_http)
	character_select_http.request_completed.connect(_on_character_select_request_completed)

	var docs_http := HTTPRequest.new()
	docs_http.name = "KnowledgeDocsRequest"
	add_child(docs_http)
	docs_http.request_completed.connect(_on_knowledge_docs_request_completed)

	var loadout_http := HTTPRequest.new()
	loadout_http.name = "CharacterLoadoutRequest"
	add_child(loadout_http)
	loadout_http.request_completed.connect(_on_character_loadout_request_completed)

	poll_timer = Timer.new()
	poll_timer.wait_time = 5.0
	poll_timer.autostart = true
	poll_timer.timeout.connect(func() -> void: _fetch_game_state(state_http))
	add_child(poll_timer)

	_bind_controls()
	_bind_hex_grid_selection()
	_fetch_characters()
	_connect_combat_stream()
	set_process(true)
	_fetch_game_state(state_http)


func _process(_delta: float) -> void:
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
				_apply_vfx(event_data)

func _apply_vfx(event_data: Dictionary) -> void:
	var type: String = str(event_data.get("type", ""))
	if type == "SERVICE_DAMAGED" or type == "BUG_SPAWNED":
		_shake_screen(0.2, 15.0)
	elif type == "JULES_CLOUD_BUILDING":
		_pulse_jules()

func _shake_screen(duration: float, intensity: float) -> void:
	var camera: Camera3D = get_node_or_null("Camera3D")
	if not camera: return
	var original_pos: Vector3 = camera.position
	var t: float = 0.0
	while t < duration:
		camera.position = original_pos + Vector3(randf_range(-1,1), randf_range(-1,1), randf_range(-1,1)) * intensity * (1.0 - t/duration) * 0.01
		await get_tree().process_frame
		t += get_process_delta_time()
	camera.position = original_pos

func _pulse_jules() -> void:
	if not has_node("HexGridManager"): return
	var grid: Node3D = $HexGridManager
	for key in grid._service_nodes.keys():
		if key.ends_with("::service-jules"):
			var model: Node3D = grid._service_nodes[key].get("model")
			if is_instance_valid(model):
				var tween = create_tween()
				var orig_scale = model.scale
				tween.tween_property(model, "scale", orig_scale * 1.2, 0.1).set_trans(Tween.TRANS_BOUNCE)
				tween.tween_property(model, "scale", orig_scale, 0.2)

func _bind_hex_grid_selection() -> void:
	if has_node("HexGridManager"):
		$HexGridManager.knowledge_node_selected.connect(_on_knowledge_node_selected)

func _bind_controls() -> void:
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/CharacterSelector"):
		$CanvasLayer/HUD/Margin/VBox/Actions/CharacterSelector.item_selected.connect(_on_character_selected)
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/DispatchQuestButton"):
		$CanvasLayer/HUD/Margin/VBox/Actions/DispatchQuestButton.pressed.connect(func() -> void:
			_send_control_command(COMMAND_ASSIGN_MISSION, _selected_agent_id, "repo-root", "Stabilize service mesh")
		)
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/PauseButton"):
		$CanvasLayer/HUD/Margin/VBox/Actions/PauseButton.pressed.connect(func() -> void:
			_send_control_command(COMMAND_PAUSE_AGENT, _selected_agent_id, "repo-root", "Hold position")
		)
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/ResumeButton"):
		$CanvasLayer/HUD/Margin/VBox/Actions/ResumeButton.pressed.connect(func() -> void:
			_send_control_command(COMMAND_RESUME_AGENT, _selected_agent_id, "repo-root", "Rejoin formation")
		)
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/PatchButton"):
		$CanvasLayer/HUD/Margin/VBox/Actions/PatchButton.pressed.connect(func() -> void:
			_send_control_command(COMMAND_PATCH_SERVICE, _selected_agent_id, "service-gateway", "Apply hot patch")
		)
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/RollbackButton"):
		$CanvasLayer/HUD/Margin/VBox/Actions/RollbackButton.pressed.connect(func() -> void:
			_send_control_command(COMMAND_ROLLBACK_SERVICE, _selected_agent_id, "service-web", "Rollback unstable release")
		)
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/RestartButton"):
		$CanvasLayer/HUD/Margin/VBox/Actions/RestartButton.pressed.connect(func() -> void:
			_send_control_command(COMMAND_RESTART_SERVICE, _selected_agent_id, "service-orchestrator", "Controlled restart")
		)
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/IsolateButton"):
		$CanvasLayer/HUD/Margin/VBox/Actions/IsolateButton.pressed.connect(func() -> void:
			_send_control_command(COMMAND_ISOLATE_SERVICE, _selected_agent_id, "service-guardian", "Isolate compromised node")
		)
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/Actions/ApplyButton"):
		$CanvasLayer/CharacterLab/Margin/VBox/Actions/ApplyButton.pressed.connect(func() -> void:
			_submit_character_loadout("apply")
		)
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/Actions/ConfirmButton"):
		$CanvasLayer/CharacterLab/Margin/VBox/Actions/ConfirmButton.pressed.connect(func() -> void:
			_submit_character_loadout("confirm")
		)
	_bind_loadout_dirty_tracking()

func _bind_loadout_dirty_tracking() -> void:
	_connect_loadout_text_changed("CanvasLayer/CharacterLab/Margin/VBox/PromptProfileId")
	_connect_loadout_text_changed("CanvasLayer/CharacterLab/Margin/VBox/PromptProfileVersion")
	_connect_loadout_text_changed("CanvasLayer/CharacterLab/Margin/VBox/ToolLoadoutId")
	_connect_loadout_text_changed("CanvasLayer/CharacterLab/Margin/VBox/ToolIds")
	_connect_loadout_text_changed("CanvasLayer/CharacterLab/Margin/VBox/Skills")

func _connect_loadout_text_changed(node_path: String) -> void:
	if not has_node(node_path):
		return
	var editable_field: Node = get_node(node_path)
	if editable_field is LineEdit:
		var line_edit: LineEdit = editable_field
		if not line_edit.text_changed.is_connected(_on_loadout_field_text_changed):
			line_edit.text_changed.connect(_on_loadout_field_text_changed)
		return
	if editable_field is TextEdit:
		var text_edit: TextEdit = editable_field
		if not text_edit.text_changed.is_connected(_on_loadout_field_text_changed):
			text_edit.text_changed.connect(_on_loadout_field_text_changed)

func _on_loadout_field_text_changed() -> void:
	if _is_programmatic_loadout_update:
		return
	_is_user_editing_loadout = true

func _fetch_game_state(http: HTTPRequest) -> void:
	var endpoint: String = url_base + "/api/v1/game-state"
	var err: int = http.request(endpoint)
	if err != OK:
		print("Error sending request: ", err)

func _on_state_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
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
	_render_character_lab(data)

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

func _render_character_lab(data: Dictionary) -> void:
	if not has_node("CanvasLayer/CharacterLab/Margin/VBox"):
		return
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/SelectedCharacter"):
		$CanvasLayer/CharacterLab/Margin/VBox/SelectedCharacter.text = "Selected character: %s" % _selected_character_id

	var loadout: Dictionary = data.get("selected_character_loadout", {})
	var prompt_profile: Dictionary = loadout.get("prompt_profile", {})
	var tool_loadout: Dictionary = loadout.get("tool_loadout", {})
	var doc_packs: Array = loadout.get("doc_packs", [])
	var skills: Array = loadout.get("skills", [])
	var selected_character_changed: bool = _selected_character_id != _character_lab_last_rendered_character_id
	var should_populate_editable_fields: bool = ((not _character_lab_initialized) or selected_character_changed or _character_lab_should_rehydrate_after_save) and (not _is_user_editing_loadout)

	if should_populate_editable_fields:
		_apply_character_lab_editable_fields(prompt_profile, tool_loadout, skills)
		_character_lab_initialized = true
		_character_lab_last_rendered_character_id = _selected_character_id
		_character_lab_should_rehydrate_after_save = false
		_is_user_editing_loadout = false
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/Docs"):
		var docs_text: String = str(_selected_knowledge_metadata.get("documentation", ""))
		if docs_text.is_empty() and doc_packs.size() > 0:
			docs_text = "Selected doc packs: " + JSON.stringify(doc_packs)
		$CanvasLayer/CharacterLab/Margin/VBox/Docs.text = docs_text if not docs_text.is_empty() else "Select a knowledge node to view docs."

func _apply_character_lab_editable_fields(prompt_profile: Dictionary, tool_loadout: Dictionary, skills: Array) -> void:
	_is_programmatic_loadout_update = true
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/PromptProfileId"):
		$CanvasLayer/CharacterLab/Margin/VBox/PromptProfileId.text = str(prompt_profile.get("profile_id", ""))
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/PromptProfileVersion"):
		$CanvasLayer/CharacterLab/Margin/VBox/PromptProfileVersion.text = str(prompt_profile.get("version", ""))
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/ToolLoadoutId"):
		$CanvasLayer/CharacterLab/Margin/VBox/ToolLoadoutId.text = str(tool_loadout.get("loadout_id", ""))
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/ToolIds"):
		$CanvasLayer/CharacterLab/Margin/VBox/ToolIds.text = ",".join(tool_loadout.get("tool_ids", []))
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/Skills"):
		$CanvasLayer/CharacterLab/Margin/VBox/Skills.text = _serialize_skill_entries(skills)
	_is_programmatic_loadout_update = false

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
		"payload_version": "v1",
		"agent_id": agent_id,
		"repo_id": repo_id,
		"task": task,
		"metadata": {
			"client_source": "godot-war-room",
			"client_turn": _turn_number()
		}
	}
	var headers: PackedStringArray = PackedStringArray(["Content-Type: application/json"])
	var body: String = JSON.stringify(payload)
	var err: int = $ControlCommandRequest.request(endpoint, headers, HTTPClient.METHOD_POST, body)
	if err != OK:
		print("Error sending control command: ", err)

func _on_command_request_completed(result: int, response_code: int, _headers: PackedStringArray, _body: PackedByteArray) -> void:
	var status_message: String = "Orden no confirmada"
	if result == HTTPRequest.RESULT_SUCCESS and response_code >= 200 and response_code < 300:
		status_message = "Orden despachada al Alto Mando"
	if has_node("CanvasLayer/HUD/Margin/VBox/Actions/CommandStatus"):
		$CanvasLayer/HUD/Margin/VBox/Actions/CommandStatus.text = status_message

func _fetch_characters() -> void:
	if not has_node("CharactersRequest"):
		return
	var endpoint: String = url_base + "/api/v1/characters"
	var err: int = $CharactersRequest.request(endpoint)
	if err != OK:
		print("Error sending characters request: ", err)

func _on_characters_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or response_code < 200 or response_code >= 300:
		return
	var json := JSON.new()
	if json.parse(body.get_string_from_utf8()) != OK:
		return
	var data: Dictionary = json.get_data()
	_characters = data.get("characters", [])
	_selected_character_id = str(data.get("selected_character_id", ""))
	_apply_character_options()

func _apply_character_options() -> void:
	if not has_node("CanvasLayer/HUD/Margin/VBox/Actions/CharacterSelector"):
		return
	var selector: OptionButton = $CanvasLayer/HUD/Margin/VBox/Actions/CharacterSelector
	selector.clear()
	var selected_index: int = 0
	for idx in range(_characters.size()):
		var character: Dictionary = _characters[idx]
		selector.add_item(str(character.get("display_name", "Unknown")))
		selector.set_item_metadata(idx, character)
		if str(character.get("id", "")) == _selected_character_id:
			selected_index = idx
	if _characters.size() > 0:
		selector.select(selected_index)
		_sync_selected_character(_characters[selected_index])

func _on_character_selected(index: int) -> void:
	if not has_node("CanvasLayer/HUD/Margin/VBox/Actions/CharacterSelector"):
		return
	var selector: OptionButton = $CanvasLayer/HUD/Margin/VBox/Actions/CharacterSelector
	var metadata: Variant = selector.get_item_metadata(index)
	if typeof(metadata) != TYPE_DICTIONARY:
		return
	var character: Dictionary = metadata
	_sync_selected_character(character)
	if has_node("CharacterSelectRequest"):
		var endpoint: String = url_base + "/api/v1/characters/select"
		var payload: Dictionary = {"character_id": _selected_character_id}
		var headers_json: PackedStringArray = PackedStringArray(["Content-Type: application/json"])
		$CharacterSelectRequest.request(endpoint, headers_json, HTTPClient.METHOD_POST, JSON.stringify(payload))

func _sync_selected_character(character: Dictionary) -> void:
	_selected_character_id = str(character.get("id", ""))
	_selected_agent_id = str(character.get("agent_id", _selected_agent_id))
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/SelectedCharacter"):
		$CanvasLayer/CharacterLab/Margin/VBox/SelectedCharacter.text = "Selected character: %s" % _selected_character_id

func _on_character_select_request_completed(result: int, response_code: int, _headers: PackedStringArray, _body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or response_code < 200 or response_code >= 300:
		print("Character selection request failed: ", result, " Code: ", response_code)

func _on_knowledge_node_selected(node_id: String, metadata: Dictionary) -> void:
	_selected_knowledge_node_id = node_id
	_selected_knowledge_metadata = metadata.duplicate(true)
	if str(_selected_knowledge_metadata.get("documentation", "")).is_empty() and has_node("KnowledgeDocsRequest"):
		var endpoint: String = url_base + "/api/v1/knowledge-tree/nodes/%s/documentation" % node_id
		$KnowledgeDocsRequest.request(endpoint)
	else:
		_render_knowledge_docs()

func _on_knowledge_docs_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or response_code < 200 or response_code >= 300:
		return
	var json := JSON.new()
	if json.parse(body.get_string_from_utf8()) != OK:
		return
	var payload: Dictionary = json.get_data()
	if str(payload.get("node_id", "")) == _selected_knowledge_node_id:
		_selected_knowledge_metadata["documentation"] = str(payload.get("documentation", ""))
	_render_knowledge_docs()

func _render_knowledge_docs() -> void:
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/Docs"):
		var docs_text: String = str(_selected_knowledge_metadata.get("documentation", ""))
		if docs_text.is_empty():
			docs_text = "No docs available for selected knowledge node."
		$CanvasLayer/CharacterLab/Margin/VBox/Docs.text = docs_text

func _submit_character_loadout(action: String) -> void:
	if not has_node("CharacterLoadoutRequest"):
		return
	var endpoint: String = url_base + "/api/v1/characters/loadout"
	var payload: Dictionary = {
		"character_id": _selected_character_id,
		"action": action,
		"loadout": _build_selected_loadout_payload(),
	}
	var headers_json: PackedStringArray = PackedStringArray(["Content-Type: application/json"])
	var err: int = $CharacterLoadoutRequest.request(endpoint, headers_json, HTTPClient.METHOD_POST, JSON.stringify(payload))
	if err != OK:
		print("Character loadout request failed to send: ", err)
		return
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/Status"):
		$CanvasLayer/CharacterLab/Margin/VBox/Status.text = "Status: %s..." % action

func _build_selected_loadout_payload() -> Dictionary:
	var profile_id: String = ""
	var profile_version: String = ""
	var loadout_id: String = ""
	var tool_ids: PackedStringArray = PackedStringArray()
	var skills_text: String = ""

	if has_node("CanvasLayer/CharacterLab/Margin/VBox/PromptProfileId"):
		profile_id = $CanvasLayer/CharacterLab/Margin/VBox/PromptProfileId.text.strip_edges()
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/PromptProfileVersion"):
		profile_version = $CanvasLayer/CharacterLab/Margin/VBox/PromptProfileVersion.text.strip_edges()
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/ToolLoadoutId"):
		loadout_id = $CanvasLayer/CharacterLab/Margin/VBox/ToolLoadoutId.text.strip_edges()
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/ToolIds"):
		tool_ids = _split_csv($CanvasLayer/CharacterLab/Margin/VBox/ToolIds.text)
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/Skills"):
		skills_text = $CanvasLayer/CharacterLab/Margin/VBox/Skills.text

	return {
		"prompt_profile": {
			"profile_id": profile_id,
			"version": profile_version,
		},
		"tool_loadout": {
			"loadout_id": loadout_id,
			"tool_ids": tool_ids,
		},
		"doc_packs": _build_doc_pack_payload(),
		"skills": _parse_skill_entries(skills_text),
	}

func _build_doc_pack_payload() -> Array:
	if _selected_knowledge_node_id.is_empty():
		return []
	return [{"pack_id": _selected_knowledge_node_id, "version": "selected"}]

func _split_csv(raw_text: String) -> PackedStringArray:
	var values: PackedStringArray = PackedStringArray()
	for token in raw_text.split(","):
		var item: String = token.strip_edges()
		if not item.is_empty():
			values.append(item)
	return values

func _parse_skill_entries(raw_text: String) -> Array:
	var skills: Array = []
	for line in raw_text.split("\n"):
		var row: String = line.strip_edges()
		if row.is_empty():
			continue
		var pair: PackedStringArray = row.split(":")
		if pair.size() == 0:
			continue
		var skill_id: String = pair[0].strip_edges()
		var enabled: bool = true
		if pair.size() > 1:
			enabled = pair[1].strip_edges().to_lower() != "off"
		skills.append({"skill_id": skill_id, "enabled": enabled})
	return skills

func _serialize_skill_entries(skills: Array) -> String:
	var lines: Array[String] = []
	for entry_variant in skills:
		var entry: Dictionary = entry_variant
		lines.append("%s:%s" % [str(entry.get("skill_id", "")), "on" if bool(entry.get("enabled", true)) else "off"])
	return "\n".join(lines)

func _on_character_loadout_request_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if has_node("CanvasLayer/CharacterLab/Margin/VBox/Status"):
		if result == HTTPRequest.RESULT_SUCCESS and response_code >= 200 and response_code < 300:
			var response_payload: Dictionary = {}
			var parser := JSON.new()
			if parser.parse(body.get_string_from_utf8()) == OK:
				response_payload = parser.get_data()
			var action: String = str(response_payload.get("action", "apply"))
			var status_verb: String = "applied" if action == "apply" else "confirmed"
			$CanvasLayer/CharacterLab/Margin/VBox/Status.text = "Status: loadout %s" % status_verb
			_character_lab_should_rehydrate_after_save = true
			_is_user_editing_loadout = false
			if has_node("GameStateRequest"):
				_fetch_game_state($GameStateRequest)
		else:
			$CanvasLayer/CharacterLab/Margin/VBox/Status.text = "Status: loadout save failed"
