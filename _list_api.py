import json
from app.main import app
from fastapi.openapi.utils import get_openapi
from collections import defaultdict

schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
paths = schema.get("paths", {})

tag_map = defaultdict(list)
for path, methods in sorted(paths.items()):
    for method, details in methods.items():
        tags = details.get("tags", ["Other"])
        summary = details.get("summary", "")
        params = details.get("parameters", [])
        body = details.get("requestBody", {})
        body_ref = ""
        if body:
            bc = body.get("content", {}).get("application/json", {}).get("schema", {})
            ref = bc.get("$ref", "")
            if ref:
                body_ref = ref.split("/")[-1]
            items = bc.get("items", {})
            if items:
                iref = items.get("$ref", "")
                if iref:
                    body_ref = "List[" + iref.split("/")[-1] + "]"
        qp = [p["name"] for p in params if p.get("in") == "query"]
        pp = [p["name"] for p in params if p.get("in") == "path"]
        r200 = details.get("responses", {}).get("200", details.get("responses", {}).get("201", {}))
        rc = r200.get("content", {}).get("application/json", {}).get("schema", {})
        resp_ref = rc.get("$ref", "")
        if resp_ref:
            resp_ref = resp_ref.split("/")[-1]

        tag_map[tags[0]].append({
            "m": method.upper(), "p": path, "s": summary,
            "qp": qp, "pp": pp, "b": body_ref, "r": resp_ref
        })

for tag in sorted(tag_map.keys()):
    print(f"\n=== {tag} ===")
    for e in tag_map[tag]:
        line = f'{e["m"]:7s} {e["p"]}'
        print(line)
        parts = [e["s"]]
        if e["pp"]:
            parts.append("Path: " + str(e["pp"]))
        if e["qp"]:
            parts.append("Query: " + str(e["qp"]))
        if e["b"]:
            parts.append("Body: " + e["b"])
        if e["r"]:
            parts.append("-> " + e["r"])
        sep = " | "
        print("        " + sep.join(parts))
