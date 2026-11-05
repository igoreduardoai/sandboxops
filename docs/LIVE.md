# Live deployment

- **URL:** http://64.177.13.126/
- **Provider:** Vultr Cloud Compute (Chicago), Ubuntu 24.04, 2 GB RAM
- **Service:** systemd unit `sandboxops`, Docker sandbox backend
- **Planner:** Vultr Serverless Inference, model `glm-5.3`
- **Health:** `GET /health` → `{"status":"ok","backend":"docker","planner":"vultr-inference"}`
- **Checked 2026-11-05 (America/Chicago):** bill → 551.00 verified; free-form "sum of first 50 primes" → 5117; network + infinite loop contained.
- Ephemeral hackathon VM on lablab $200 credits — treat as temporary.
