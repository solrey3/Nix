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
    services = {
        doc["metadata"]["name"]: doc["spec"]
        for doc in docs if doc["kind"] == "Service"
    }
    for name in ("jellyfin", "navidrome", "sabnzbd"):
        assert services[name]["type"] == "ClusterIP"
        assert all("nodePort" not in port for port in services[name]["ports"])
    assert services["pihole"]["type"] == "LoadBalancer"
    assert {(p["port"], p["protocol"]) for p in services["pihole"]["ports"]} == {
        (53, "TCP"), (53, "UDP")
    }
    homepage = next(doc for doc in docs if doc["kind"] == "ConfigMap")
    assert url in homepage["data"]["index.html"]


check(sys.argv[1], {"kubernetes.io/hostname": "kilo"}, "/mnt/illmatic", 1000, 100,
      'href="https://jellyfin.tail32b131.ts.net"')
check(sys.argv[2], {"homelab/storage": "media"}, '/srv/media "test"', 2000, 200,
      'href="https://media.example/?a=1&amp;b=&quot;two&quot;"')

web = list(yaml.safe_load_all(Path(sys.argv[3]).read_text()))
ingresses = {doc["metadata"]["name"]: doc for doc in web if doc["kind"] == "Ingress"}
assert set(ingresses) == {"jellyfin", "navidrome", "sabnzbd", "pihole"}
for name, doc in ingresses.items():
    assert doc["spec"]["ingressClassName"] == "tailscale"
    assert doc["spec"]["tls"] == [{"hosts": [name]}]
    assert "tailscale.com/funnel" not in doc["metadata"].get("annotations", {})
    backend = doc["spec"]["defaultBackend"]["service"]
    assert backend == {
        "name": "pihole-web" if name == "pihole" else name,
        "port": {"number": {"jellyfin": 8096, "navidrome": 4533, "sabnzbd": 8080, "pihole": 80}[name]},
    }
pihole_web = next(doc for doc in web if doc["kind"] == "Service")
assert pihole_web["metadata"]["namespace"] == "network"
assert pihole_web["spec"]["type"] == "ClusterIP"
assert pihole_web["spec"]["selector"] == {"app": "pihole"}
assert pihole_web["spec"]["ports"][0]["targetPort"] == "http"

operator = list(yaml.safe_load_all(Path(sys.argv[4]).read_text()))
assert not any(doc["kind"] == "Secret" for doc in operator)
chart = next(doc for doc in operator if doc["kind"] == "HelmChart")
assert chart["spec"]["version"] == "1.104.2"
assert chart["spec"]["targetNamespace"] == "tailscale"
values = yaml.safe_load(chart["spec"]["valuesContent"])
assert "oauth" not in values
assert values["apiServerProxyConfig"]["mode"] == "false"
assert values["proxyConfig"]["defaultTags"] == "tag:k8s"
