"""Private API fixture; no credentials, network, tag or release writes."""
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from test_forgejo_release import ProposalAPI, PLAN, SOURCE
from unittest.mock import patch
import forgejo_release as release
base = subprocess.run(['git', 'cat-file', '-e', '21759bfc12bb87520f62e5a85122cc85406a352d:scripts/forgejo_release.py'], capture_output=True)
print(json.dumps({'target': 'private Forgejo API fixture', 'base': '21759bfc', 'base_adapter_present': base.returncode == 0}))
api = ProposalAPI()
with patch.object(release, 'plan_from_git', return_value=PLAN):
    print(json.dumps({'candidate': release.propose(api, Path('.'), SOURCE), 'version': api.plan['version'], 'write_endpoints': [x[0] for x in api.writes]}))
    api.writes.clear()
    print(json.dumps({'repeat': release.propose(api, Path('.'), SOURCE), 'additional_writes': len(api.writes)}))
    api.main = 'b' * 40
    try:
        release.propose(api, Path('.'), SOURCE)
        raise AssertionError('advanced main must refuse')
    except release.Refusal as error:
        print(json.dumps({'negative_advanced_main': str(error), 'additional_writes': len(api.writes)}))
