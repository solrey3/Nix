"""Validate both default and overridden generated Kubernetes manifests."""
import sys
from pathlib import Path

import yaml


def check(path, selector, mount, uid, gid, url):
    text = Path(path).read_text()
    assert "@NODE_SELECTOR@" not in text
    docs = list(yaml.safe_load_all(text))
    deployments = {
        doc["metadata"]["name"]: doc["spec"]["template"]["spec"]
        for doc in docs if doc["kind"] == "Deployment"
    }
    for name in ("jellyfin", "navidrome", "pihole"):
        assert deployments[name]["nodeSelector"] == selector
    for spec in deployments.values():
        for volume in spec.get("volumes", []):
            if "hostPath" in volume and volume["hostPath"]["path"] != "/dev/dri":
                assert volume["hostPath"]["path"].startswith(mount + "/")
    env = {
        entry["name"]: entry.get("value")
        for entry in deployments["sabnzbd"]["containers"][0]["env"]
    }
    assert env["PUID"] == str(uid)
    assert env["PGID"] == str(gid)
    homepage = next(doc for doc in docs if doc["kind"] == "ConfigMap")
    assert url in homepage["data"]["index.html"]


check(sys.argv[1], {"kubernetes.io/hostname": "kilo"}, "/mnt/illmatic", 1000, 100,
      'href="http://kilo.local:8096"')
check(sys.argv[2], {"homelab/storage": "media"}, '/srv/media "test"', 2000, 200,
      'href="https://media.example/?a=1&amp;b=&quot;two&quot;"')
