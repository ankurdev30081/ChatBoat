import httpx

from app.config import settings

SYSTEM_PROMPT = (
    "You are a helpful property assistant answering questions about DarGlobal and Wasalt "
    "real estate developments, using only the context provided below. "
    "If the answer isn't in the context, say you don't have that information rather than guessing. "
    "Be concise and cite which project/page the info comes from when relevant."
)

# OpenRouter's free-tier models share a rate-limited upstream pool and can return
# 429s sporadically; fall back through a couple of alternates before giving up.
FALLBACK_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "minimax/minimax-m3:free",
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

    models_to_try = [settings.openrouter_model] + [m for m in FALLBACK_MODELS if m != settings.openrouter_model]

    async with httpx.AsyncClient(timeout=60) as client:
        last_error: Exception | None = None
        for model in models_to_try:
            resp = await _call_model(client, model, messages)
            if resp.status_code == 429:
                last_error = httpx.HTTPStatusError(
                    f"{model} rate-limited", request=resp.request, response=resp
                )
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        raise last_error or RuntimeError("No OpenRouter model available")
