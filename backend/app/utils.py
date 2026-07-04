from fastapi.routing import APIRoute


def simple_generate_unique_route_id(route: APIRoute) -> str:
    """Generate simplified operation IDs from route names."""
    return route.name
