"""OpenAPI schema customization for drf-spectacular."""

TAG_RULES = (
    ("/api/auth/", "Authentication"),
    ("/api/profiles/discover/", "Discovery"),
    ("/api/profiles/", "Profiles"),
    ("/api/matching/", "Matching"),
    ("/api/chat/", "Chat"),
)


def postprocess_tag_groups(result, generator, request, public):
    """Assign tags to operations based on URL prefix."""
    paths = result.get("paths", {})
    for path, path_item in paths.items():
        tag = "API"
        for prefix, name in TAG_RULES:
            if path.startswith(prefix):
                tag = name
                break

        for method, operation in path_item.items():
            if method.startswith("x-") or not isinstance(operation, dict):
                continue
            operation["tags"] = [tag]

    return result
