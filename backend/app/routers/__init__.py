from . import analyze, demos, export, health, locations, resources, timeseries, variables, weather

ALL_ROUTERS = [
    health.router,
    variables.router,
    resources.router,
    locations.router,
    weather.router,
    timeseries.router,
    analyze.router,
    demos.router,
    export.router,
]
