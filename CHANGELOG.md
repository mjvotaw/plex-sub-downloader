# CHANGELOG

## 0.2.2 - 08/09/2023

### Changes
- Fixed issue where "Special" season episodes throw a ValueError
- Fixed typos in README
- Removed addic7ed as a supported subtitle provider (Subliminal apparently hasn't supported it for years)

## 0.2.1 - 04/08/2023

### Changes
- Fixed a really dumb problem caused by the fact that I forgot that Python assigned lists by reference.
- Fixed a different, but also really dumb problem, where uploadSubtitlesToMetadata was immediately overwriting the `subtitles` variable
- Added a new command, `check-video` to allow for manually checking a specific Movie, Episode, Season, or Show for missing subtitles.

## 0.2.0 - 04/01/2023

### Changes
- Decided to write a Changelog.
- Moved away from Flask's built-in server to waitress.
- Added methods to check and add the webhook url to Plex's webhooks.
- Removed printing of `provider_configs` when debug printing is enabled.
- Updated python version requirement to >=3.8