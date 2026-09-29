// Radial profiles r(theta) measured pixel-by-pixel from the reference video.
// Adapted from jeremy-prt/bloub (MIT, Copyright (c) 2026 Jérémy Perret),
// src/bot/profiles.ts. Generated there by tools/extract-profiles.py.
//
// theta = 0 points right and grows clockwise (y is down). Unit: radius of the
// resting ball = 1. Do not round these numbers — they are measurements.

export const PROFILE_SAMPLES = 64

export const PROFILES = {
  // Triangle, apex up, very rounded corners. Frame 190, measured footprint
  // 1.995 x 1.884. Used by the bloub `play`/`orbit` states; our disruption
  // silhouette carries it over unchanged.
  triangle: [0.7819,0.8211,0.8747,0.9440,1.0223,1.0960,1.1401,1.1340,1.0808,1.0047,0.9265,0.8603,0.8104,0.7730,0.7450,0.7273,0.7151,0.7118,0.7148,0.7245,0.7427,0.7680,0.8037,0.8518,0.9148,0.9876,1.0583,1.1073,1.1109,1.0667,0.9940,0.9164,0.8482,0.7948,0.7555,0.7261,0.7056,0.6925,0.6859,0.6869,0.6938,0.7084,0.7305,0.7615,0.8040,0.8595,0.9311,1.0092,1.0791,1.1171,1.1054,1.0501,0.9779,0.9050,0.8450,0.7990,0.7656,0.7413,0.7258,0.7160,0.7146,0.7204,0.7330,0.7528],
} as const

export type ProfileName = keyof typeof PROFILES
