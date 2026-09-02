import logging
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a helpful property assistant answering questions about DarGlobal and Wasalt "
    "real estate developments, using only the context provided below. "
    "If the answer isn't in the context, say you don't have that information rather than guessing. "
    "Be concise and cite which project/page the info comes from when relevant."
)

FALLBACK_MODELS = [
    "minimax/minimax-m3:free",
    "openrouter/free",
    "minimax/minimax-m2.7:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]


async def _call_model(client: httpx.AsyncClient, model: str, messages: list[dict]) -> httpx.Response:
    return await client.post(
        f"{settings.openrouter_base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        },
        json={"model": model, "messages": messages},
    )


async def chat_completion(context: str, history: list[dict], user_message: str) -> str:
    messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\nContext:\n{context}"}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # Ordered list of models to try, starting with the configured model
    models_to_try = [settings.openrouter_model] + [m for m in FALLBACK_MODELS if m != settings.openrouter_model]

    async with httpx.AsyncClient(timeout=60) as client:
        last_error: Exception | None = None
        for model in models_to_try:
            try:
                resp = await _call_model(client, model, messages)
                if resp.status_code != 200:
                    logger.warning(f"Model {model} returned HTTP {resp.status_code}: {resp.text[:200]}")
                    last_error = httpx.HTTPStatusError(
                        f"{model} returned HTTP {resp.status_code}", request=resp.request, response=resp
                    )
                    continue

                data = resp.json()
                if "error" in data:
                    err_msg = data.get("error", {}).get("message", str(data["error"]))
                    logger.warning(f"Model {model} returned API error: {err_msg}")
                    last_error = RuntimeError(f"{model} error: {err_msg}")
                    continue

                choices = data.get("choices")
                if not choices or not isinstance(choices, list) or len(choices) == 0:
                    logger.warning(f"Model {model} returned no choices: {data}")
                    last_error = RuntimeError(f"{model} returned empty choices")
                    continue

                content = choices[0].get("message", {}).get("content")
                if content:
                    return content
                else:
                    logger.warning(f"Model {model} returned empty content: {choices[0]}")
                    last_error = RuntimeError(f"{model} returned empty content")
                    continue

            except Exception as e:
                logger.warning(f"Error calling model {model}: {e}")
                last_error = e
                continue

        raise last_error or RuntimeError("No OpenRouter model available")
