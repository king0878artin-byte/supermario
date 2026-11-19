
[app]

title = Super Mario
package.name = supermario
package.domain = org.artin

source.dir = .
source.include_exts = py,kv,png,jpg
version = 1.0

requirements = python3,kivy

orientation = landscape
fullscreen = 0

android.api = 35
android.minapi = 26
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]

log_level = 2
warn_on_root = 1
