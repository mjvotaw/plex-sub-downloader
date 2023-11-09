import os
import tempfile
import socket
from .subliminalHelper import SubliminalHelper
from subliminal.video import Video as SubVideo
from subliminal.subtitle import Subtitle
from .PlexWebhookEvent import PlexWebhookEvent
import logging
import plexapi
from plexapi.video import Video, EpisodeSession
from plexapi.library import LibrarySection
from plexapi.media import SubtitleStream
from .plexHelper import PlexHelper

log = logging.getLogger('plex-sub-downloader')

class PlexSubDownloader:

    def __init__(self):
        self.config = None
        self.sub = None
        self.plexHelper = None

    def configure(self, config):
        """initializes and configures the needed classes for PlexSubDownloader to work.
        :param object config: config json. See config.schema.json for structure.
        :return: True if everything initializes correctly, otherwise False.
        """

        log.info("Configuring PlexSubDownloader")
        self.config = config
        self.subtitle_destination = config.get('subtitle_destination', 'with_media')
        self.format_priority = config.get('format_priority', None)
        if self.format_priority is not None and len(self.format_priority) == 0:
            self.format_priority = None

        self.sub = SubliminalHelper(
            providers= config.get('subtitle_providers', None),
            provider_configs=config.get('subtitle_provider_configs', None),
            format_priority=self.format_priority
            )
        
        self.plexHelper = PlexHelper(baseurl=config['plex_base_url'], 
                                     token=config['plex_auth_token'], 
                                     host=config.get('host', '0.0.0.0'), 
                                     port=config.get('port', None))
        
        if config['subtitle_destination'] == 'with_media' and self.plexHelper.checkLibraryPermissions() == False:
            log.error("One or more of the Plex libraries are not readable/writable by the current user.")
            return False
        return True
        

    def handleWebhookEvent(self, event):
        """Handles the given webhook event. 
        :param PlexWebhookEvent event:
        """
        log.debug("handleWebhookEvent")
        log.debug("Event type: " + event.event)
        if self.config.get("save_plex_webhook_events", False):
            save_dir = self.config.get("save_plex_webhook_events_dir", None)
            if save_dir is not None:
                self.saveWebhookEvent(event, save_dir)
        
        if event.event == "library.new":
            self.handleLibraryNewEvent(event)

    def handleLibraryNewEvent(self, event):
        """Handles webhook events of type library.new.
        Retrieves the relevent item from Plex and searches for subtitles.
        :param PlexWebhookEvent event:
        """
        log.info("Handling library.new event")
        log.info(f'Title: {event.Metadata.title}, type: {event.Metadata.type}, section: {event.Metadata.librarySectionTitle}')
        
        video = self.plexHelper.getVideoItemFromEvent(event)
        if video is None:
            log.info("Video referenced in event could not be retrieved.")
            return
        
        self.handleDownloadingVideoSubtitles(video)

    def manuallyCheckVideoSubtitles(self, video_key):
        """Manually check video for missing subtitles, and try to download missing subs.
        """

        video = self.plexHelper.getVideoItem(video_key)
        if video is None:
            log.info(f"Video with key {video_key} could not be retrieved.")
            return 
        self.handleDownloadingVideoSubtitles(video)

    def handleDownloadingVideoSubtitles(self, video):
        missingVideos = self.getVidsMissingSubtitles([video])
        log.info("Found " + str(len(missingVideos)) + " videos missing subtitles")
        log.info([f'{video.title}, {video.key}' for video in missingVideos])
        if len(missingVideos) > 0:
            subtitles = self.downloadSubtitlesForVideos(missingVideos)

            if self.subtitle_destination == "metadata":
                self.uploadSubtitlesToMetadata(missingVideos, subtitles)
            else:
                self.sub.save_subtitles(subtitles)
        else:
            log.info("No subtitles to download, doing nothing!")
        
    def getVidsMissingSubtitles(self,videos):
        """Search the given list of videos for ones that don't already have subtitles.
        For videos of type 'season' or 'show', this will search through all of the episodes
        as well.
        :param list videos: list of plexapi.video.Video objects.
        :return: list of Video objects that don't have any subtitles.
        """

        vidsMissingSubs = []
        for v in videos:
            if v.type == 'movie' or v.type == 'episode':
                if self.isVideoMissingSubtitles(v):
                    vidsMissingSubs.append(v)
                
            elif v.type == 'season' or v.type == 'show':
                eps = v.episodes()
                for e in eps:
                    e.reload()
                    if self.isVideoMissingSubtitles(e):
                        vidsMissingSubs.append(e)

        return vidsMissingSubs

    def isVideoMissingSubtitles(self, video):
        """Checks the given video to see if it's missing subtitles for any of the languages defined in config['languages'].
        :param video: plexapi.video.Video object
        :return: boolean, False if the video has subtitles for every requested language, True otherwise
        """

        missingSubtitles = self.getMissingSubtitleLanguages(video)
        return len(missingSubtitles) > 0
    
    def getMissingSubtitleLanguages(self, video):
        """Compares the existing subtitle languages on the video to the languages requested based on config['languages'],
        and returns requested languages that aren't already present.
        :param video: plexapi.video.Video object
        :return: array of language codes
        """
        requestedLanguages = self.config['languages'].copy()

        subtitles = video.subtitleStreams()
        
        for subtitle in subtitles:
            if self.format_priority is not None and subtitle.format not in self.format_priority:
                continue
            if subtitle.languageCode in requestedLanguages:
                requestedLanguages.remove(subtitle.languageCode)

        log.info(f'Video {video.title} {video.key} is missing {len(requestedLanguages)} subtitle languages:')
        log.info(f'{requestedLanguages}')

        return requestedLanguages

    def downloadSubtitlesForVideos(self, videos):
        """Attempts to download subtitles for the given list of videos.
        :param list videos: list of plexapi.video.Video objects.
        :return: dict[subliminal.video.Video, list[subliminal.subtitle.Subtitle]]
        """

        log.info(f"Downloading subtitles for {len(videos)} videos:")
        log.info([video.title for video in videos])
        missing_languages = [self.getMissingSubtitleLanguages(video) for video in videos]
        subtitles = self.sub.search_videos(videos, missing_languages)
        return subtitles

    def uploadSubtitlesToMetadata(self, plexVideos, subtitleDict):
        """Saves the subtitles to Plex.
        :param list plexVideos: list of plexapi.video.Video objects.
        :param dict subtitles: dict of dict[subliminal.video.Video, list[subliminal.subtitle.Subtitle]]
        """

        log.info("Saving subtitles to Plex metadata")
        tempdir = tempfile.gettempdir()
        for video in plexVideos:
            mediaPart = video.media[0].parts[0]
            filepath = video.media[0].parts[0].file
            for subVideo, subtitles in subtitleDict.items():
                if subVideo.name == filepath:
                    log.debug(f'found {len(subtitles)} subtitles for video {subVideo.name}')
                    if len(subtitles) == 0:
                        continue
                    savedSubtitlePaths = self.sub.save_subtitle(subVideo, subtitles, destination=tempdir)
                    for subtitlePath in savedSubtitlePaths:
                        log.debug(f'Uploading subtitles \'{subtitlePath}\' to video {video.title} {video.key}')
                        originalDefault = None 
                        existingSubs = video.subtitleStreams();
                        for sub in existingSubs:
                            if sub.default:
                                originalDefault = sub
                                break

                        video.uploadSubtitles(subtitlePath)
                        try:
                            if originalDefault is not None:
                                mediaPart.setSelectedSubtitleStream(originalDefault)
                            else:
                                mediaPart.resetSelectedSubtitleStream()
                        except Exception as e:
                            log.debug('Error when trying to set default subtitle stream. This probably isn\'t a big deal?')
                            log.debug(e)
                            
    def checkWebhookRegistration(self):
        return self.plexHelper.checkWebhookRegistration()
    
    def addWebhookToPlex(self):
        return self.plexHelper.addWebhookToPlex()
        
    def saveWebhookEvent(self, event, dir):
        import json
        import time
        
        webhook_filename = f'event_{int(time.time())}_{event.event}.json'
        filepath = os.path.join(dir, webhook_filename)
        with open(filepath, 'w') as fp:
            log.debug(f'Saving webhook event to {filepath}')
            json.dump(event._data, fp, indent=4)

