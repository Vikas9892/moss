"""Drop-in check: does the stock OpenAI Python client work by only changing base_url + key?"""
import json, traceback
from openai import OpenAI
from common import BASE, PID, PKEY, RESULTS, log, md_table

client = OpenAI(base_url=BASE, api_key=f"{PID}:{PKEY}")
FAST = "moss/fastlane-1"
rows = []


def check(name, fn):
    try:
        ok, note = fn()
    except Exception as e:  # record, don't stop
        ok, note = False, f"{type(e).__name__}: {str(e)[:200]}"
        log(f"compat_{name}_exception", {"trace": traceback.format_exc()})
    rows.append([name, "PASS" if ok else "FAIL", note]); print(rows[-1], flush=True)


def models_list():
    ids = [m.id for m in client.models.list().data]
    log("compat_models", ids)
    return len(ids) > 0, f"{len(ids)} models: {', '.join(ids[:6])}..."


def chat_basic(model=FAST):
    r = client.chat.completions.create(model=model, messages=[{"role": "user", "content": "Reply with the word pong."}], max_tokens=10)
    log(f"compat_chat_{model.replace('/', '_')}", r.model_dump())
    t = r.choices[0].message.content or ""
    return "pong" in t.lower(), repr(t[:60])


def chat_stream():
    chunks = list(client.chat.completions.create(model=FAST, stream=True, max_tokens=30,
                                                 messages=[{"role": "user", "content": "Count 1 to 5."}]))
    text = "".join((c.choices[0].delta.content or "") for c in chunks if c.choices)
    return bool(text), f"{len(chunks)} chunks, {text[:40]!r}"


TOOLS = [{"type": "function", "function": {"name": "get_weather", "description": "Weather for a city",
                                           "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}]


def tools(model=FAST):
    r = client.chat.completions.create(model=model, tools=TOOLS, messages=[{"role": "user", "content": "What's the weather in Pune?"}])
    log(f"compat_tools_{model.replace('/', '_')}", r.model_dump())
    tc = r.choices[0].message.tool_calls or []
    args = json.loads(tc[0].function.arguments) if tc else {}
    return bool(tc) and "pune" in json.dumps(args).lower(), f"tool_calls={[t.function.name for t in tc]} args={args}"


def tool_roundtrip():
    msgs = [{"role": "user", "content": "What's the weather in Pune?"}]
    r = client.chat.completions.create(model=FAST, tools=TOOLS, messages=msgs)
    tc = r.choices[0].message.tool_calls
    msgs += [r.choices[0].message.model_dump(exclude_none=True),
             {"role": "tool", "tool_call_id": tc[0].id, "content": '{"temp_c": 31, "sky": "hazy"}'}]
    r2 = client.chat.completions.create(model=FAST, tools=TOOLS, messages=msgs)
    t = r2.choices[0].message.content or ""
    return "31" in t, repr(t[:80])


SCHEMA = {"type": "json_schema", "json_schema": {"name": "city", "strict": True, "schema": {
    "type": "object", "properties": {"city": {"type": "string"}, "country": {"type": "string"}, "population_millions": {"type": "number"}},
    "required": ["city", "country", "population_millions"], "additionalProperties": False}}}


def json_schema(model=FAST):
    r = client.chat.completions.create(model=model, response_format=SCHEMA, messages=[{"role": "user", "content": "Describe Tokyo."}])
    d = json.loads(r.choices[0].message.content)
    return set(d) == {"city", "country", "population_millions"}, json.dumps(d)[:80]


def responses_basic():
    r = client.responses.create(model=FAST, input="Reply with the word pong.")
    log("compat_responses", r.model_dump())
    return "pong" in r.output_text.lower(), repr(r.output_text[:60])


def responses_stream():
    types = [e.type for e in client.responses.create(model=FAST, input="Count 1 to 3.", stream=True)]
    return types[-1] == "response.completed", f"{len(types)} events, last={types[-1]}"


def main():
    check("models.list", models_list)
    check("chat basic (fastlane)", chat_basic)
    for m in ["openai/gpt-6-luna", "anthropic/claude-haiku-5.5", "google/gemini-3.5-flash-lite"]:
        check(f"chat basic ({m})", lambda m=m: chat_basic(m))
    check("chat streaming", chat_stream)
    check("function tool call (fastlane)", tools)
    check("function tool call (claude-haiku)", lambda: tools("anthropic/claude-haiku-5.5"))
    check("tool result round-trip", tool_roundtrip)
    check("json_schema output (fastlane)", json_schema)
    check("json_schema output (claude-haiku)", lambda: json_schema("anthropic/claude-haiku-5.5"))
    check("responses.create", responses_basic)
    check("responses streaming", responses_stream)
    (RESULTS / "compat.md").write_text("## OpenAI SDK drop-in compatibility\n" + md_table(["check", "result", "detail"], rows), encoding="utf-8")


if __name__ == "__main__":
    main()
