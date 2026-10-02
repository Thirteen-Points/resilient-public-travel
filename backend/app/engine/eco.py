"""Explicitly simulated mode coefficients, not measured passenger outcomes."""
import math

# g CO2 / passenger-km; seat chance and nominal crowding are demo assumptions.
CO2_G_PER_KM = {"MTR": 35, "BUS": 90, "MINIBUS": 120, "FERRY": 180, "WALK": 0}
SEAT_CHANCE = {"MTR": .35, "BUS": .55, "MINIBUS": .8, "FERRY": .8, "WALK": 1.0}
CV = {"MTR": .08, "BUS": .35, "MINIBUS": .30, "FERRY": .25, "WALK": .15}


def estimates(mode, distance_m, duration_s, capacity_factor=1.0, weather=False, *, cv=None):
    seat = SEAT_CHANCE[mode]
    standing = (1 - seat) * duration_s
    comfort = seat * math.exp(-standing / 3600) * max(0, min(1, capacity_factor))
    sigma = duration_s * (CV[mode] if cv is None else cv) * (1.3 if weather and mode in {"BUS", "FERRY"} else 1)
    return {"co2_g": distance_m / 1000 * CO2_G_PER_KM[mode], "comfort": comfort,
            "sigma_s": sigma, "provenance": "simulated"}
