Plex Sub Downloader
===================


## What is it?

This is a command-line tool designed to automate the downloading of subtitles for media on your [Plex Media Server](https://www.plex.tv/). It makes use of [Flask](https://flask.palletsprojects.com/en/2.1.x/) and [Python-PlexAPI](https://github.com/pkkid/python-plexapi) to listen for newly-added media, and [Subliminal](https://github.com/Diaoul/subliminal) to search your favorite subtitle providers.

## Okay, Cool, but Why?

Plex has built-in Agents for downloading subtitles from OpenSubtitles.org, but it doesn't search for subtitles automatically, and, more importantly, doesn't support VIP accounts (which means you're stuck reading ads _in your subtitles!_).

Plex Plugins like [Sub-Zero](https://github.com/pannal/Sub-Zero.bundle) are getting increasingly complicated to install and use, as Plex has been threatening to completely phase out plugins since 2018.

And there's other tools like [Bazarr](https://github.com/bazarr/), which works best if you've already bought into the [Sonarr](https://sonarr.tv/)/[Radarr](https://radarr.video/) ecosystem. But, honestly, while these tools are great, I find them to be over-built for what I want to do.

I just wanted something that tries to download subtitles for new media added to my Plex server, and that's it.

<br />

---------------

## Requirements
- Requires python >=3.8
- You'll need to purchase [Plex Pass](https://www.plex.tv/plex-pass/) to enable [push notifications](https://support.plex.tv/articles/push-notifications/) and [webhooks](https://support.plex.tv/articles/115002267687-webhooks/) 

----------------
<br />

# Setup

### NOTE: This project is still VERY MUCH a work in progress. The setup process will hopefully be easier in a future release. ###

<br />

First, install plex_sub_downloader:
```
pip3 install plex_sub_downloader
```
Then, find an auth token for your Plex account:
  https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/


Then, create a config.json file somewhere:

```
{
    "plex_base_url": "<url to your plex server, ie http://localhost:32400>",
    "plex_auth_token": "<your auth token here>",
    "languages": [
        "eng"
    ],
    "webhook_host": "0.0.0.0",
    "webhook_port": <some port number, default = 5000>
}
```

- Next, run `configtest` on this config file to make sure it's formatted correctly
```
plex_sub_downloader --config path/to/config.json configtest
```

You should get a result like:
```
2022-07-16 21:08:38:plex_sub_downloader:INFO - Testing config file '/path/to/config.json'
2022-07-16 21:08:38:plex_sub_downloader:INFO - config file is valid.
```

<br />

# Running the Webhook Listener Thing

To start plex_sub_downloader in webhook mode, run:
```
plex_sub_downloader --config path/to/config.json start-webhook
``` 

Assuming it starts and runs correctly, you should see something like the following:
```
 2023-04-01 15:51:01:PlexSubDownloader:INFO - Configuring PlexSubDownloader
2023-04-01 15:51:01:plex_sub_downloader:INFO - plex-sub-downloader starting up
2023-04-01 15:51:01:PlexSubDownloader:INFO - Checking if webhook url http://192.168.1.248:5000/webhook has been added to Plex...
2023-04-01 15:51:02:PlexSubDownloader:INFO - webhook url http://192.168.1.248:5000/webhook has been added to Plex
 ```
If it says `webhook url {webhookUrl} has been added to Plex`, then congrats, things worked right.

If instead it says `Could not add the webhook url {webhookUrl} to Plex. You may need to manually add this through the web dashboard.`, then try the following:

The url you'll need to add to Plex will be `http://<ip address>:<port>/webhook`. 

- Open Plex, navigate to Settings, and select Webhooks from the left-hand menu. 
- Click 'Add Webhook' and add your webhook url.

<br />

# Verifying that the Webhook Works

To verify that Plex can call your webhook, re-run the above startup command, and add the `--debug` flag, then start playing a video on Plex. You'll get a big dump of data, starting with:
```
2022-07-16 21:28:14:PlexSubDownloader:DEBUG - handleWebhookEvent
2022-07-16 21:28:14:PlexSubDownloader:DEBUG - Event type: media.play
```

# Verifying that Subtitles Can Get Downloaded

To verify that subtitles can be downloaded, add something new to your library. Within about 10-20 seconds, you should see output like:
```
2022-07-19 14:14:30:PlexSubDownloader:INFO - Handling library.new event
2022-07-19 14:14:30:PlexSubDownloader:INFO - Title: Wild Wild West, type: movie, section: Movies
2022-07-19 14:14:30:PlexSubDownloader:INFO - Found 1 videos missing subtitles
2022-07-19 14:14:30:PlexSubDownloader:INFO - ['Wild Wild West, /library/metadata/45525']
2022-07-19 14:14:30:PlexSubDownloader:INFO - Downloading subtitles for 1 videos
2022-07-19 14:14:30:PlexSubDownloader:INFO - ['Wild Wild West']
2022-07-19 14:14:32:PlexSubDownloader:INFO - Saving subtitles to Plex metadata
2022-07-19 14:14:32:PlexSubDownloader:INFO - found 1 for video /path/to/movies/Wild.Wild.West.1999/Wild.Wild.West.1999.mp4
```

Congrats! It's probably working?

<br />

# Manually Running for a Specific Video

plex_sub_downloader also has a command for manually checking a Movie, Episode, Season, or Show for missing subtitles.
Simply run plex_sub_downloader with the `check-video` command option, and pass it the item's metadata key:

```
plex_sub_downloader --config path/to/config.json check-video /library/metadata/42069
```

# Command-line Arguments

| Argument | Description |
| -------- | ----------- |
| -h, --help | Show this help message and exits |
| -v, --version | Prints version info and exits |
| -c CONFIG, --config CONFIG | Config File |
| -d, --debug | Enable debug logging |
| configtest | Run validation on config file |
| start-webhook | Run http webhook server |
| check-video {video key} | Manually check the given video for missing subtitles. |

<br />

# Configuration

| Parameter | Required? | Description |
| --------- | --------- | ----------- |
| plex_base_url | Required |Base url to reach your Plex Media Server (ie `"http://127.0.0.1:32400"`) |
| plex_auth_token | Required |Authentication token, needed to send requests to your server. |
| subtitle_providers | Required | List of subtitle providers to search. Currently, this really is only guaranteed to work with `"opensubtitles"` and `"opensubtitlesvip"`. Subliminal supports `"legendastv", "opensubtitles", "opensubtitlesvip", "podnapisi", "shooter", "thesubdb", "tvsubtitles"`, so you're welcome to try any of those if you want. |
|subtitle_provider_configs | Required | Dictionary of configuration parameters for your chosen subtitle providers. Each provider may support different config parameters. See [Subliminal's documentation](https://subliminal.readthedocs.io/en/latest/api/providers.html) for more details. |
| webhook_host | Optional, default `"127.0.0.1"` | The hostname to listen on. By default, the server will only be accessible from the computer running it. Set this to `"0.0.0.0"` to make it publicly available on your network.|
| webhook_port | Optional, default `5000` | the port to listen on. |
| subtitle_destination | Optional, default `"with_media"` | Either `"with_media"` or `"metadata"`. `"with_media"` will save subtitle files alongside the media files. `"metadata"` will upload the subtitles to Plex, which stores the subtitles as part of the media's metadata. If Plex and PlexSubDownloader don't run on the same server, you'll need to set this to `"metadata"`.
| languages | Optional, default `["eng"]` | Array of [ISO 639-3 language tags](https://en.wikipedia.org/wiki/List_of_ISO_639-3_codes) to download subtitles for.|
| format_priority | Optional, default `None` | Array of subtitle formats (file extensions, without the ".") that should be prioritized. PlexSubDownloader will ignore any existing subtitles with formats not listed and will try to find subtitles in one of the formats listed. [Plex fully supports](https://support.plex.tv/articles/200471133-adding-local-subtitles-to-your-media/) `"srt", "smi", "ssa", "ass"`, and `"vtt"` formats. |
| log_level | Optional, default `INFO` | The log level to set [Python's logging](https://docs.python.org/3/howto/logging.html). Expects a string value, one of `"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"`. |


### Example configuration:

```
{
    "plex_base_url": "http://127.0.0.1:32400",
    "plex_auth_token": "<token-goes-here>"
    "webhook_host": "0.0.0.0",
    "webhook_port": 6669,
    "subtitle_destination": "metadata",
    "languages": [
        "eng"
    ],
    "format_priority": [
        "srt", 
        "smi"
    ],
    "subtitle_providers": [
        "opensubtitlesvip"
    ],
    "subtitle_provider_configs": {
        "opensubtitlesvip": {
            "username": "<username here>",
            "password": "<password here>"
        }
    },
    "log_level": "DEBUG"
}
```
