from app.manifest.loader import load_manifest


def test_manifest_loads():
    m = load_manifest()
    assert m.version
    assert len(m.servers) > 0
    ids = {s.id for s in m.servers}
    assert len(ids) == len(m.servers)


def test_manifest_secret_fields_typed():
    m = load_manifest()
    for s in m.servers:
        for ev in s.env_vars:
            if ev.secret:
                assert ev.type == "password", f"{s.id}.{ev.name}: secret should be password type"
