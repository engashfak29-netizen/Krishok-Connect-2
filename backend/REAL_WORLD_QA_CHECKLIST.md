# Real-World QA Checklist

## Devices
- Android Chrome: low-end, mid-range, flagship
- iPhone Safari: current and one prior iOS release
- PWA install / uninstall / relaunch
- Camera, microphone, notifications, background/foreground

## Network
- Stable 4G
- Weak 4G
- 3G
- 2G / throttled bandwidth
- High latency
- Packet loss
- Disconnect/reconnect during upload, chat, call and checkout

## Load
Run `python ops/load_test.py https://YOUR-DOMAIN 100 1000`, then repeat at concurrency 500 and 1000 with infrastructure sized for the test. Record p50/p95/p99 latency, error rate, CPU, RAM, DB connections and Redis health.

## Security
Use an authorized DAST/pentest suite against staging first. Verify RBAC/IDOR, upload validation, OTP abuse, password reset, webhook replay/signature checks, WebSocket authorization, CORS, headers, rate limits and private media access.

## Agriculture / AI
Use an expert-reviewed dataset of Bangladesh crops, varieties, pests, diseases, growth stages, local names, verified interventions and approved doses. Measure diagnosis accuracy and unsafe-answer rate before enabling autonomous recommendations.
