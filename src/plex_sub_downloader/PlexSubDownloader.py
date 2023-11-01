import os
import tempfile
import socket
from .subliminalHelper import SubliminalHelper
from subliminal.video import Video as SubVideo
from subliminal.subtitle import Subtitle
from .PlexWebhookEvent import PlexWebhookEvent
import logging
import plexapi
from plexapi.server import PlexServer
from plexapi.video import Video
from plexapi.library import LibrarySection
from plexapi.media import SubtitleStream


log = logging.getLogger('plex-sub-downloader')

class PlexSubDownloader:

    def __init__(self):
        self.config = None
        self.sub = None
        self.plexServe = None

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
        
        self.plexServer = PlexServer(baseurl=config['plex_base_url'], token=config['plex_auth_token'])
        
        if config['subtitle_destination'] == 'with_media' and self.checkLibraryPermissions() == False:
            log.error("One or more of the Plex libraries are not readable/writable by the current user.")
            return False
        return True
        

    def handleWebhookEvent(self, event):
        """Handles the given webhook event. 
        :param PlexWebhookEvent event:
        """
        log.debug("handleWebhookEvent")
        log.debug("Event type: " + event.event)

        if event.event == "library.new":
            self.handleLibraryNewEvent(event)

    def handleLibraryNewEvent(self, event):
        """Handles webhook events of type library.new.
        Retrieves the relevent item from Plex and searches for subtitles.
        :param PlexWebhookEvent event:
        """
        log.info("Handling library.new event")
        log.info(f'Title: {event.Metadata.title}, type: {event.Metadata.type}, section: {event.Metadata.librarySectionTitle}')
        
        video = self.getVideoItemFromEvent(event)
        if video is None:
            log.info("Video referenced in event could not be retrieved.")
            return
        
        self.handleDownloadingVideoSubtitles(video)

    def manuallyCheckVideoSubtitles(self, video_key):
        """Manually check video for missing subtitles, and try to download missing subs.
        """

        video = self.getVideoItem(video_key)
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
        
    def getVideoItemFromEvent(self, event):
         # if Metadata.type == "show", then the metadata key looks like
        # `/library/metadata/45533/children`, which doesn't return what we actually want
        # when we call fetchItem
        key = event.Metadata.key
        return self.getVideoItem(key)
    
    def getVideoItem(self, key):
        key = key.replace("/children", "")
        try:
            video = self.plexServer.fetchItem(ekey=key)
            video.reload()
            return video
        except Exception as e:
            log.error(f'Error while trying to retrieve video with key {key}')
            log.error(e)
            return None
    

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
                                mediaPart.setDefaultSubtitleStream(originalDefault)
                            else:
                                mediaPart.resetDefaultSubtitleStream()
                        except Exception as e:
                            log.debug('Error when trying to set default subtitle stream. This probably isn\'t a big deal?')
                            log.debug(e)
                            

    def checkLibraryPermissions(self, sectionId=None):
        """Checks whether the application has permissions to read/write to the base paths of each section 
        within Plex's library.
        :param string sectionId: An optional id value to just check permissions of a single section.
        :return: True if all sections are read/writeable, otherwise False.
        """

        log.debug("Checking library permissions")
        sections = []

        checkedOk = True
        if sectionId != None:
            sections = [self.plexServer.library.sectionByID(sectionId)]
        else:
            sections = self.plexServer.library.sections()

        for section in sections:
            locations = section.locations
            for location in locations:
                exists = os.path.exists(location)
                if not exists:
                    log.error(f'Error checking library permissions. Directory \'{location}\' doesnt exist?')
                    checkedOk = False
                else:
                    read_access = os.access(location, os.R_OK)
                    write_access = os.access(location, os.W_OK)
                    if not read_access or not write_access:
                        log.error(f'Error checking library permissions. Cannot read/write to directory \'{location}\'')
                        checkedOk = False
        
        return checkedOk
    
    def checkWebhookRegistration(self):
        
        webhookUrl = self.getWebhookUrl()
        log.info(f'Checking if webhook url {webhookUrl} has been added to Plex...')

        plexAccount = self.plexServer.myPlexAccount()
        webhooks = plexAccount.webhooks()

        if webhookUrl in webhooks:
            log.info(f'webhook url {webhookUrl} has been added to Plex')
            return True
        else:
            log.info(f'webhook url {webhookUrl} has NOT been added to Plex')
            return False
    
    def addWebhookToPlex(self):
        webhookUrl = self.getWebhookUrl()
        plexAccount = self.plexServer.myPlexAccount()
        log.info(f'Attempting to add webhook url {webhookUrl} to Plex...')
        webhooks = plexAccount.addWebhook(webhookUrl)
        if webhookUrl in webhooks:
            log.info('Webhook url successfully added!')
            return True
        else:
            log.error(f'Could not add the webhook url {webhookUrl} to Plex. You may need to manually add this through the web dashboard.')
            return False

    def getWebhookUrl(self):
        host = self.getExternalHost()
        port = self.config.get('webhook_port', None)
        if port is not None:
            port = f":{port}"

        webhookUrl = f"http://{host}{port}/webhook"
        return webhookUrl
    
    def getExternalHost(self):
        host = self.config.get('webhook_host', '0.0.0.0')
        
        if host == "0.0.0.0":
            external_host = self.get_interface_ip(socket.AF_INET)
            return external_host
        elif host == "::":
            external_host = self.get_interface_ip(socket.AF_INET6)
            return external_host
        else:
            return host

    def get_interface_ip(self, family: socket.AddressFamily) -> str:
        """Get the IP address of an external interface. Used when binding to
        0.0.0.0 or ::1 to show a more useful URL.
        :meta private:
        """
        # arbitrary private address
        host = "fd31:f903:5ab5:1::1" if family == socket.AF_INET6 else "10.253.155.219"

        with socket.socket(family, socket.SOCK_DGRAM) as s:
            try:
                s.connect((host, 58162))
            except OSError:
                return "::1" if family == socket.AF_INET6 else "127.0.0.1"

            return s.getsockname()[0]  # type: ignore



