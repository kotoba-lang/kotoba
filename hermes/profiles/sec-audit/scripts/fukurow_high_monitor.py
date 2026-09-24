#!/usr/bin/env python3
"""Monitor output for the fukurow high-alert watch (deterministic, no timestamps).
Prints 'high=N medium=M' or 'api_error'. Used as the cronjob change-detector:
the agent only wakes when this output changes."""
import json, subprocess

p = subprocess.run(['gh', 'api',
                    'repos/com-junkawasaki/fukurow/dependabot/alerts?state=open&per_page=100'],
                   capture_output=True, text=True)
if p.returncode != 0:
    print('api_error')
else:
    alerts = json.loads(p.stdout)
    high = sum(1 for a in alerts if a['security_advisory']['severity'] == 'high')
    medium = sum(1 for a in alerts if a['security_advisory']['severity'] == 'medium')
    print('high=%d medium=%d' % (high, medium))
