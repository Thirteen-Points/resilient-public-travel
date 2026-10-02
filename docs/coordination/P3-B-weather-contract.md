# T7.5 weather factors: B to C

`data/weather_impact.json` is a **simulated coefficient table**, not verified Hong Kong transport performance data. Even `normal` is a neutral model baseline. HKO warnings can identify a condition, but do not validate these coefficients.

For C's route engine: consume `weather_conditions[condition].mode_penalties` and `walk_speed_factor` only after mapping a reviewed weather event to a known condition. Values above 1 are estimated penalties. A value of **0 means unavailable/suspended**, never zero travel time or zero cost. Keep the current accessibility hard filters in place before rescoring. Unknown condition should use `normal`, and output must keep a simulated/estimated label. Recalculate on an approved weather event or its expiration/revocation. B does not alter C's graph or scoring code in this round.

Open verification: exercise one approved weather event and its expiry through C's route query, then confirm changed and restored ETA/availability plus the estimated label in A's page. The present file and tests validate the data contract only.
