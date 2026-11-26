## Streaming latency (chat/completions, max_tokens=60, X-Moss-Cache: off, sequential, client in India)
| model | ok | TTFT p50 ms | TTFT p95 ms | total p50 ms | total p95 ms |
|---|---|---|---|---|---|
| moss/fastlane-1 | 20/20 | 486 | 603 | 742 | 951 |
| openai/gpt-6-luna | 19/20 | 1298 | 1607 | 1585 | 1794 |
| anthropic/claude-haiku-5.5 | 20/20 | 1099 | 4579 | 1316 | 4865 |
| google/gemini-3.5-flash-lite | 20/20 | 1378 | 6188 | 1395 | 6190 |
| deepseek/deepseek-v4.1-flash | 20/20 | 1300 | 1441 | 1404 | 2047 |

## Reply cache (same prompt twice, X-Moss-Cache: on)
| model | TTFT 1st | TTFT 2nd | total 1st | total 2nd | identical text |
|---|---|---|---|---|---|
| moss/fastlane-1 | 479 | 522 | 527 | 523 | True |
| openai/gpt-6-luna | 1522 | 525 | 1559 | 526 | True |