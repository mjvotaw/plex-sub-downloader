# CHANGELOG

## 0.3.1 - 12/30/2023

### Changes
- **Breaking Change** `host` and `port` config options have been renamed `webhook_host` and `webhook_port`, so that they match literally all of the documentation that I wrote for this.
- Defaults of `127.0.0.1` and `5000` for the `webhook_host` and `webhook_port`, respectively actually work now.

## 0.3.0 - 11/08/2023

### Changes
- Added a new `set_next_episode_subtitles` config option (see README)
- Refactored plexapi communication out of PlexSubDownloader class into PlexHelper class
- Refactored method names in PlexSubDownloader and PlexHelper to snake_case
- Fixed an issue introduced in 0.2.4 that was preventing subtitles from being downloaded

## 0.2.4 - 11/01/2023

### Changes
- Added a new `format_priority` config option, which tells PlexSubDownloader to only download subtitles of the specified formats
- Added hash generation for subtitle providers as needed (this requires that PlexSubDownloader can access the video file)
- Removed some debug logs that would potentially log sensitive information
- Updated `log_level` config option to support string values (ie `"DEBUG"`, `"INFO"`, etc) instead of having to use the literal integer values (which still work)

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