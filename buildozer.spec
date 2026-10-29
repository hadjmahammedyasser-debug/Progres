[app]
title = Progres Repas
package.name = progresrepas
package.domain = org.yasser
source.dir = .
source.include_exts = py,json
version = 1.0
requirements = python3,kivy==2.3.0,requests,urllib3,chardet,idna,certifi,charset-normalizer
orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 0
