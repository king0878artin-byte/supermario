# SuperMario

A touch-friendly 2D platform game built with Python and Kivy for Android.

## Features

- 100 unlockable stages with four visual themes and multiple platform layouts.
- Persistent per-level best scores and a maximum of three stars per stage.
- Star thresholds: 500 points = 1 star, 1,500 points = 2 stars, 3,000 points = 3 stars.
- Replaying a stage only replaces its saved result when the new score is higher.
- Animated procedural player sprite with running movement.
- Solid pipes, pipe-top collisions, and pipe travel using the DOWN / PIPE control.
- Walking enemies, moving turtle enemies, shell stomps, and boss fights every ten stages.
- Original generated sound effects and a looping chiptune-style background track.
- Main menu, level selection screen, locked-stage indicators, and saved star display.
- Three lives, score, best score, power-ups, and stage progression.

## Controls

- LEFT / RIGHT: Move.
- JUMP: Jump and stomp enemies.
- DOWN / PIPE: Enter a nearby pipe while standing on the ground.
- RESTART: Restart the current stage.
- MENU: Pause and return to the main menu.

## Build APK

The GitHub Actions workflow builds the Android APK automatically after a push to main.

Open Actions → Build SuperMario APK, then download the supermario-apk artifact from a successful run.

## Save data

Scores, stage unlocks, and star records are stored locally in the app's private data directory. They remain available when the app is closed and reopened, but uninstalling the app may erase them.
