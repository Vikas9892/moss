## OpenAI SDK drop-in compatibility
| check | result | detail |
|---|---|---|
| models.list | PASS | 19 models: moss/fastlane-1, openai/gpt-6-luna, openai/gpt-6.1-terra, openai/gpt-6.1-sol, openai/gpt-6-astra, anthropic/claude-haiku-5.5... |
| chat basic (fastlane) | PASS | 'pong' |
| chat basic (openai/gpt-6-luna) | PASS | 'pong' |
| chat basic (anthropic/claude-haiku-5.5) | PASS | 'pong' |
| chat basic (google/gemini-3.5-flash-lite) | PASS | 'pong' |
| chat streaming | PASS | 8 chunks, '1, 2, 3, 4, 5' |
| function tool call (fastlane) | PASS | tool_calls=['get_weather'] args={'city': 'Pune'} |
| function tool call (claude-haiku) | PASS | tool_calls=['get_weather'] args={'city': 'Pune'} |
| tool result round-trip | PASS | 'The weather in Pune is currently hazy with a temperature of 31°C.' |
| json_schema output (fastlane) | PASS | {"city": "Tokyo", "country": "Japan", "population_millions": 14.148862136999998} |
| json_schema output (claude-haiku) | PASS | {"city": "Tokyo", "country": "Japan", "population_millions": 14.0} |
| responses.create | PASS | 'pong' |
| responses streaming | PASS | 12 events, last=response.completed |