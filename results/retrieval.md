## Retrieval grounding (index of 10 fictional facts, built in 6.3s, status `{"created_at": "2026-11-25T15:34:43.926Z", "completed_at": "2026-11-25T15:34:48.`)
| model | X-Moss-Indexes | correct | total p50 ms | X-Moss-Retrieve-Ms p50 | prompt tokens p50 |
|---|---|---|---|---|---|
| moss/fastlane-1 | no | 1/11 | 587 | 0 | 102 |
| moss/fastlane-1 | yes | 11/11 | 569 | 10 | 449 |
| anthropic/claude-haiku-5.5 | no | 0/11 | 1447 | 0 | 50 |
| anthropic/claude-haiku-5.5 | yes | 11/11 | 1074 | 10 | 335 |

### Wrong answers with the index attached
none