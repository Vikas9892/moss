## Inference API edge cases
| case | expected | actual |  | error message |
|---|---|---|---|---|
| no auth header | 401 | 401 authentication_error | ok | Missing bearer token |
| wrong key | 401 | 401 authentication_error | ok | The project credentials were rejected |
| bearer without colon | 401 | 401 authentication_error | ok | Send Bearer project_id:project_key |
| unknown model | 400 model_not_found | 400 model_not_found | ok | Unknown model moss/nope-9. Send model moss/fastlane-1, or a vendor model name with your ow |
| empty messages | 400 | 400 invalid_request_error | ok | messages is required |
| messages missing | 400 | 400 invalid_request_error | ok | messages is required |
| unknown top-level field (chat) | 400 | 200 | **MISMATCH** |  |
| max_tokens negative | 400 | 400 invalid_request_error | ok | max_tokens must be at least 1, got -5. (parameter=max_tokens, value=-5) |
| max_tokens 10M (> 262k window) | 400 | 400 context_length_exceeded | ok | max_tokens=10000000 cannot be greater than max_model_len=262144. Please request fewer outp |
| temperature 5 | 400 | 400 invalid_request_error | ok | temperature must be in [0, 2], got 5.0. (parameter=temperature, value=5.0) |
| n=3 (one choice only) | 400 | 400 invalid_request_error | ok | n must be 1. This endpoint returns one choice. |
| image part to fastlane (text only) | 400 | 400 invalid_request_error | ok | At most 0 image(s) may be provided in one prompt. (parameter=image) |
| openai: seed refused | 400 unsupported_parameter | 400 unsupported_parameter | ok | seed is not supported for model openai/gpt-6-luna. Remove it from the request. |
| anthropic: temperature refused | 400 unsupported_parameter | 400 unsupported_parameter | ok | temperature is not supported for model anthropic/claude-haiku-5.5. Remove it from the requ |
| anthropic: json_object refused | 400 unsupported_parameter | 400 unsupported_parameter | ok | response_format is not supported for model anthropic/claude-haiku-5.5. Remove it from the  |
| temperature=1 counts as unset (anthropic) | 200 | 200 | ok |  |
| nonexistent index | 403 | 403 permission_error | ok | X-Moss-Indexes names an index outside this project |
| 33 indexes (max 32) | 400 | 403 permission_error | **MISMATCH** | X-Moss-Indexes names an index outside this project |
| empty index names ',,,' | 400 | 200 | **MISMATCH** |  |
| path-like index name | 403 | 403 permission_error | ok | X-Moss-Indexes names an index outside this project |
| X-Moss-Retrieve: banana | 400 | 200 | **MISMATCH** |  |
| BYOK garbage provider key (openai) | 401 | 401 upstream_error | ok | The model rejected the prompt: HTTP 401: Incorrect API key provided: sk-garbage. You can f |
| BYOK key on fastlane | 400 | 200 | **MISMATCH** |  |
| responses: previous_response_id | 400 | 400 unsupported_parameter | ok | previous_response_id is not supported. Send the whole conversation in input. |
| responses: background=true | 400 | 400 unsupported_parameter | ok | background true is not supported |
| responses: OpenAI built-in web_search tool | 400 | 400 unsupported_parameter | ok | tools[0] of type web_search is not supported |
| responses: unknown field | 400 | 400 unsupported_parameter | ok | foo is not supported |
| mcp tool with http (not https) url | 400 | 400 mcp_server_error | ok | server_url must use https |
| mcp tool pointing at localhost (SSRF probe) | 400 | 400 mcp_server_error | ok | server_url host 127.0.0.1 is not on the public internet |
| body 4.3 MB | 413 | None  | **MISMATCH** |  |
| ~300k-token prompt to fastlane | 400 context_length_exceeded | 400 context_length_exceeded | ok | 939 ms to reject |
| 25 parallel requests (burst 10) | some 429 w/ Retry-After | 15x429, 10x200, Retry-After={'1'} | ok | [200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 429, 429, 429, 429, 429, 429, 429, 429, 429, 429, 429, 429, 429, 429, 429] |