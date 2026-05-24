"""
Test de eficiencia de tokens para el sistema con Gemini API.
Mide: tokens consumidos, cache hits, tamaño de prompts, y costo estimado.
"""
import os
import sys
import time
import json
import hashlib
from collections import OrderedDict
from typing import Any, Dict, List, Optional

# Configurar la API key de Gemini (desde env o argumento CLI)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or (sys.argv[1] if len(sys.argv) > 1 else "")
if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY no configurada. Usa: GEMINI_API_KEY=<key> python test_gemini_token_efficiency.py")
    sys.exit(1)
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

import litellm
litellm.telemetry = False
litellm.set_verbose = False

MODEL = "gemini/gemini-3-flash-preview"  # default del sistema, confirmado disponible

# ─── helpers ────────────────────────────────────────────────────────────────

def count_tokens_approx(text: str) -> int:
    """Estimación rápida: ~4 chars per token."""
    return max(1, len(text) // 4)

def call_gemini(messages: List[Dict], label: str = "", json_mode: bool = False) -> Dict[str, Any]:
    """Llama a Gemini y retorna métricas de tokens."""
    start = time.time()
    kwargs: Dict[str, Any] = dict(
        model=MODEL,
        messages=messages,
        temperature=0.1,
        max_tokens=512,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        response = litellm.completion(**kwargs)
        elapsed = time.time() - start
        usage = response.usage
        content = response.choices[0].message.content or ""
        return {
            "label": label,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "elapsed_s": round(elapsed, 2),
            "content_preview": content[:120].replace("\n", " "),
            "success": True,
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "label": label,
            "error": str(e)[:200],
            "elapsed_s": round(elapsed, 2),
            "success": False,
        }

def print_result(r: Dict):
    if r["success"]:
        print(f"  ✅ [{r['label']}]")
        print(f"     Tokens  → prompt={r['prompt_tokens']}  completion={r['completion_tokens']}  total={r['total_tokens']}")
        print(f"     Tiempo  → {r['elapsed_s']}s")
        print(f"     Preview → {r['content_preview']}")
    else:
        print(f"  ❌ [{r['label']}] ERROR: {r['error']}")

# ─── Prueba 1: prompt corto vs largo ────────────────────────────────────────

def test_prompt_length():
    print("\n📏 TEST 1: Prompt corto vs largo\n")

    short_messages = [
        {"role": "system", "content": "Responde brevemente."},
        {"role": "user", "content": "¿Qué es Python?"},
    ]
    long_system = (
        "Eres un experto en ingeniería de software con 20 años de experiencia. "
        "Tienes conocimientos profundos en Python, Java, C++, Rust, Go, JavaScript, "
        "TypeScript, Ruby, PHP, Swift, Kotlin, Scala y muchos otros lenguajes. "
        "Responde siempre de manera exhaustiva, detallada y técnicamente precisa. "
        "Incluye ejemplos de código cuando sea posible. Usa formato Markdown. "
        "Considera siempre las mejores prácticas de la industria. " * 5
    )
    long_messages = [
        {"role": "system", "content": long_system},
        {"role": "user", "content": "¿Qué es Python?"},
    ]

    r1 = call_gemini(short_messages, "Prompt corto (system ~5 tokens)")
    r2 = call_gemini(long_messages, "Prompt largo (system ~200 tokens)")

    print_result(r1)
    print_result(r2)

    if r1["success"] and r2["success"]:
        overhead = r2["prompt_tokens"] - r1["prompt_tokens"]
        ratio = r2["prompt_tokens"] / max(r1["prompt_tokens"], 1)
        print(f"\n  📊 Overhead del prompt largo: +{overhead} tokens ({ratio:.1f}x más tokens de entrada)")
        if overhead > 150:
            print("  ⚠️  El sistema prompt es muy verboso. Reducirlo ahorraría tokens.")
        else:
            print("  ✅ El overhead es razonable.")

# ─── Prueba 2: cache LRU en memoria ─────────────────────────────────────────

def test_lru_cache():
    print("\n🗃️  TEST 2: LRU Cache en memoria (simulación del sistema)\n")

    cache: OrderedDict = OrderedDict()
    CACHE_MAX = 10
    hits = 0
    misses = 0
    total_tokens_saved = 0

    def get_key(messages):
        return hashlib.md5(json.dumps(messages, sort_keys=True).encode()).hexdigest()

    def cached_call(messages, label):
        nonlocal hits, misses, total_tokens_saved
        key = get_key(messages)
        if key in cache:
            hits += 1
            cache.move_to_end(key)  # mark as most-recently used
            saved = cache[key]["total_tokens"]
            total_tokens_saved += saved
            print(f"  💾 CACHE HIT [{label}] → ahorró {saved} tokens")
            return cache[key]
        misses += 1
        result = call_gemini(messages, label)
        if result["success"]:
            if len(cache) >= CACHE_MAX:
                cache.popitem(last=False)
            cache[key] = result
        return result

    base_messages = [
        {"role": "system", "content": "Responde en una oración."},
        {"role": "user", "content": "¿Cuál es la capital de Francia?"},
    ]
    unique_messages = [
        [{"role": "system", "content": "Responde en una oración."},
         {"role": "user", "content": "¿Cuál es la capital de Alemania?"}],
        [{"role": "system", "content": "Responde en una oración."},
         {"role": "user", "content": "¿Cuál es la capital de Japón?"}],
    ]

    # Primera llamada (miss)
    r = cached_call(base_messages, "Francia - 1ª llamada")
    print_result(r)

    # Segunda llamada idéntica (hit)
    cached_call(base_messages, "Francia - 2ª llamada (esperado HIT)")

    # Llamadas únicas
    for i, msgs in enumerate(unique_messages):
        r = cached_call(msgs, f"Pregunta única #{i+1}")
        if r["success"]:
            print(f"  ✅ [{r['label']}] total={r['total_tokens']} tokens")

    # Tercera llamada a base (hit de nuevo)
    cached_call(base_messages, "Francia - 3ª llamada (esperado HIT)")

    print(f"\n  📊 Resultado del cache: hits={hits}, misses={misses}")
    print(f"     Tokens ahorrados por cache: {total_tokens_saved}")
    efficiency = hits / max(hits + misses, 1) * 100
    print(f"     Hit rate: {efficiency:.0f}%")
    if efficiency >= 30:
        print("  ✅ El cache LRU reduce tokens correctamente.")
    else:
        print("  ⚠️  Hit rate bajo. Considera pre-poblar el cache con prompts frecuentes.")

# ─── Prueba 3: respuesta JSON vs texto libre ─────────────────────────────────

def test_json_mode():
    print("\n🔧 TEST 3: JSON mode (API) vs texto libre\n")

    # Same messages for both calls — only the API-level response_format differs.
    # This isolates the effect of structured-output mode from prompt wording.
    messages = [
        {"role": "system", "content": "Responde brevemente."},
        {"role": "user", "content": "Lista 3 lenguajes de programación populares."},
    ]

    r1 = call_gemini(messages, "Texto libre (json_mode=False)", json_mode=False)
    r2 = call_gemini(messages, "JSON mode API (json_mode=True)", json_mode=True)
    print_result(r1)
    print_result(r2)

    if r1["success"] and r2["success"]:
        diff = r1["completion_tokens"] - r2["completion_tokens"]
        print(f"\n  📊 JSON mode ahorra ~{diff} completion tokens vs texto libre")
        if diff > 0:
            print("  ✅ El modo JSON API reduce tokens de salida.")
        else:
            print("  ℹ️  Texto libre fue igual o más conciso en este caso.")

# ─── Prueba 4: fallback de modelos ──────────────────────────────────────────

def test_model_fallback():
    print("\n🔄 TEST 4: Comparación de modelos (eficiencia relativa)\n")

    models_to_test = [
        "gemini/gemini-2.0-flash-lite",   # más barato / menor latencia
        "gemini/gemini-3-flash-preview",  # default del sistema
        "gemini/gemini-3.5-flash",        # más capaz de la familia flash
    ]
    messages = [
        {"role": "system", "content": "Responde en máximo 2 oraciones."},
        {"role": "user", "content": "Explica qué es un grafo de conocimiento."},
    ]

    results = []
    for m in models_to_test:
        start = time.time()
        try:
            resp = litellm.completion(model=m, messages=messages, temperature=0.1, max_tokens=256)
            elapsed = time.time() - start
            usage = resp.usage
            results.append({
                "model": m,
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "elapsed_s": round(elapsed, 2),
                "success": True,
            })
            print(f"  ✅ {m}")
            print(f"     total={usage.total_tokens} tokens | {round(elapsed,2)}s")
        except Exception as e:
            elapsed = time.time() - start
            results.append({"model": m, "error": str(e)[:150], "elapsed_s": round(elapsed,2), "success": False})
            print(f"  ❌ {m}: {str(e)[:100]}")

    ok = [r for r in results if r["success"]]
    if len(ok) >= 2:
        fastest = min(ok, key=lambda r: r["elapsed_s"])
        cheapest = min(ok, key=lambda r: r["total_tokens"])
        print(f"\n  📊 Modelo más rápido: {fastest['model']} ({fastest['elapsed_s']}s)")
        print(f"     Modelo con menos tokens: {cheapest['model']} ({cheapest['total_tokens']} total)")

# ─── Resumen final ───────────────────────────────────────────────────────────

def print_summary():
    print("\n" + "="*60)
    print("📋 DIAGNÓSTICO DE EFICIENCIA DE TOKENS – RESUMEN")
    print("="*60)
    print("""
El sistema actualmente:

  ✅ Tiene LRU cache en memoria (100 slots) en LLMService
  ✅ Usa litellm con soporte nativo para Gemini
  ✅ Tiene fallback entre modelos Gemini
  ✅ Usa json_mode para reducir completion tokens en structured calls

Posibles mejoras de eficiencia:
  ⚠️  gemini-3-flash-preview puede no existir → fallback a 1.5-flash consume más
  ⚠️  Los system prompts en prompt_optimizer.py son largos (~300 tokens)
  ⚠️  No hay prefix caching explícito (Gemini soporta context caching)
  ⚠️  El modelo de fallback usa openrouter (costo +20% overhead)
""")

# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🚀 Iniciando prueba de eficiencia de tokens con Gemini API")
    print(f"   Modelo base: {MODEL}")
    print(f"   API Key: {GEMINI_API_KEY[:8]}...")

    test_prompt_length()
    test_lru_cache()
    test_json_mode()
    test_model_fallback()
    print_summary()
