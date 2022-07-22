Plex Sub Downloader
===================


What is it?
-----------

This is a command-line tool designed to automate the downloading of subtitles for media on your [Plex Media Server](https://www.plex.tv/). It makes use of [Flask](https://flask.palletsprojects.com/en/2.1.x/) and [Python-PlexAPI](https://github.com/pkkid/python-plexapi) to listen for newly-added media, and [Subliminal](https://github.com/Diaoul/subliminal) to search your favorite subtitle providers.

Okay, Cool, but Why?
--------------------

Plex has built-in Agents for downloading subtitles from OpenSubtitles.org, but it doesn't search for subtitles automatically, and, more importantly, doesn't support VIP accounts (which means you're stuck reading ads _in your subtitles!_).

Plex Plugins like [Sub-Zero](https://github.com/pannal/Sub-Zero.bundle) are getting increasingly complicated to install and use, as Plex has been threatening to completely phase out plugins since 2018.

And there's other tools like [Bazarr](https://github.com/bazarr/), which works best if you've already bought into the [Sonarr](https://sonarr.tv/)/[Radarr](https://radarr.video/) ecosystem. But, honestly, while these tools are great, I find them to be over-built for what I want to do.

I just wanted something that tries to download subtitles for new media added to my Plex server, and that's it.

---
Requirements
------------
---
- Requires python >=3.6
- You'll need to purchase [Plex Pass](https://www.plex.tv/plex-pass/) to enable [webhooks](https://support.plex.tv/articles/115002267687-webhooks/) 

---
Setup
-----
---
### NOTE: This project is still VERY MUCH a work in progress. The setup process will hopefully be easier in the next release. ###
-----------------


- First, install plex_sub_downloader:
```
pip3 install plex_sub_downloader
```
- Then, find an auth token for your Plex account:
  https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/


- Then, create a config.json file somewhere:

```
{
    "plex_base_url": "<url to your plex server, ie http://localhost:32400>",
    "plex_auth_token": "<your auth token here>",
    "subliminal": {
        "languages": [
            "eng"
        ]
    },
    "webhook_host": "0.0.0.0",
    "webhook_port": <some port number, default = 5000>
}
```

- Next, run `configtest` on this config file to make sure it's formatted correctly
```
plex_sub_downlaoder --config path/to/config.json configtest
```

You should get a result like:
```
2022-07-16 21:08:38:plex_sub_downloader:INFO - Testing config file '/path/to/config.json'
2022-07-16 21:08:38:plex_sub_downloader:INFO - config file is valid.
```

- Next, we need to get the url to add to Plex. Run plex_sub_downloader with the `start-webhook` flag: 

```
plex_sub_downloader --config path/to/config.json start-webhook --debug
``` 

Assuming it starts and runs correctly, the last few lines should look like
```
 * Serving Flask app 'plex_sub_downloader.plex_sub_downloader' (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
 * Debug mode: off
 * Running on all addresses.
   WARNING: This is a development server. Do not use it in a production deployment.
 * Running on http://<ip address>:<port>/ (Press CTRL+C to quit)
 ```

The url you'll need to add to Plex will be `http://<ip address>:<port>/webhook`. 

- Open Plex, navigate to Settings, and select Webhooks from the left-hand menu. Add your webhook url.

- To verify that Plex can call your webhook, start playing a video. You'll get a big dump of data, starting with:
```
2022-07-16 21:28:14:PlexSubDownloader:DEBUG - handleWebhookEvent
2022-07-16 21:28:14:PlexSubDownloader:DEBUG - Event type: media.play
<some ip addr> - - [16/Jul/2022 21:28:14] "POST /webhook HTTP/1.1" 200 -
```

- To verify that subtitles can be downloaded, add something new to your library. Within about 10-20 seconds, you should see output like:
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

---
Command-line Arguments
----------------------
---
| Argument | Description |
| -------- | ----------- |
| -h, --help | show this help message and exit |
| -c CONFIG, --config CONFIG | Config File |
| -d, --debug | Enable debug logging |
| configtest | Run validation on config file |
| start-webhook| Run http webhook server |


---
Configuration
-------------
---

| Parameter | Required? | Description |
| --------- | --------- | ----------- |
| plex_base_url | Yes |Base url to reach your Plex Media Server (ie `"http://127.0.0.1:32400"`) |
| plex_auth_token | Yes |Authentication token, needed to send requests to your server. |
| webhook_host | optional, default `"127.0.0.1"` | the hostname to listen on. By default, the server will only be accessible from the computer running it. Set this to `"0.0.0.0"` to make it publicly available on your network.|
| webhook_port | Optional, default `5000` | the port to listen on. |
| subtitle_destination | Optional, default `"with_media"` | Either `"with_media"` or `"metadata"`. `"with_media"` will save subtitle files alongside the media files. `"metadata"` will upload the subtitles to Plex, which stores the subtitles as part of the media's metadata. If Plex and PlexSubDownloader don't run on the same server, you'll need to set this to `"metadata"`.
| languages | Optional, default `["en"]` | Array of [IETF language tags](https://en.wikipedia.org/wiki/IETF_language_tag#List_of_common_primary_language_subtags) to download subtitles for.|
| subtitle_providers | Optional, defaults to all | List of subtitle providers to search. Currently, Subliminal supports `"addic7ed", "legendastv", "opensubtitles", "opensubtitlesvip", "podnapisi", "shooter", "thesubdb", "tvsubtitles"`. |
|subtitle_provider_configs | Optional, default None | Dictionary of configuration parameters for your chosen subtitle providers. Each provider may support different config parameters. See [Subliminal's documentation](https://subliminal.readthedocs.io/en/latest/api/providers.html) for more details. |
| log_level | Optional, default logging.INFO | log level. Expects an integer value. 


### Example configuration:

```
{
    "plex_base_url": "http://127.0.0.1:32400",
    "plex_auth_token": "<token-goes-here>"
    "webhook_host": "0.0.0.0",
    "webhook_port": 6669,
    "subtitle_destination": "metadata",
    "languages": [
        "eng",
        "es"
    ],
    "subtitle_providers": [
        "opensubtitlesvip",
        "tvsubtitles"
    ],
    "subtitle_provider_configs": {
        "opensubtitlesvip": {
            "username": "<username here>",
            "password": "<password here>"
        }
    },
    "log_level": 20
}
```

---
Roadmap
-------
---

- [] Implement Plex auth instead of requiring that users find an auth token on their own.
- [] Make application register itself as webhook listener