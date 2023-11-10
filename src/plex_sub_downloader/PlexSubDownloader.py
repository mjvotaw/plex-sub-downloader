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
        
        if config['subtitle_destination'] == 'with_media' and self.plexHelper.check_library_permissions() == False:
            log.error("One or more of the Plex libraries are not readable/writable by the current user.")
            return False
        return True
        

    def handle_webhook_event(self, event):
        """Handles the given webhook event. 
        :param PlexWebhookEvent event:
        """
        log.debug("handleWebhookEvent")
        log.debug("Event type: " + event.event)
        if self.config.get("save_plex_webhook_events", False):
            save_dir = self.config.get("save_plex_webhook_events_dir", None)
            if save_dir is not None:
                self.save_webhook_event(event, save_dir)
        
        if event.event == "library.new":
            self.handle_library_new_event(event)
        elif event.event == "media.play" or event.event == "media.resume":
            self.handle_video_play_event(event)

    def handle_library_new_event(self, event):
        """Handles webhook events of type library.new.
        Retrieves the relevent item from Plex and searches for subtitles.
        :param PlexWebhookEvent event:
        """
        log.info("Handling library.new event")
        log.info(f'Title: {event.Metadata.title}, type: {event.Metadata.type}, section: {event.Metadata.librarySectionTitle}')
        
        video = self.plexHelper.get_video_item_from_event(event)
        if video is None:
            log.info("Video referenced in event could not be retrieved.")
            return
        
        self.handle_downloading_video_subtitles(video)

    def handle_video_play_event(self, event):
        """Handles webhook events of type media.play and media.resume.
            If `set_next_episode_subtitles` is set to True in config, attempts to set subtitles 
            for the next episode in the series (assuming that the event is for an Episode).
            :param PlexWebhookEvent event:
        """
        if self.config.get('set_next_episode_subtitles', False) == False or event.Metadata.type != "episode":
            return
        
        log.info(f"Handling {event.event} event")
        log.info(f'Title: {event.Metadata.title}, type: {event.Metadata.type}, section: {event.Metadata.librarySectionTitle}')

        session = self.plexHelper.get_session_for_play_event(event)
        if session is None or type(session) is not EpisodeSession:
            log.debug("No session found for this event. Skipping")
            return
        
        next_episode = self.plexHelper.get_next_episode(session.key)
        if next_episode is None:
            log.debug("No next episode for this session. Skipping")
            return
        
        subtitle_stream = self.plexHelper.get_selected_subtitles_for_play_session(session)
        if subtitle_stream is None:
            log.debug("No subtitles set for this session. Setting next episode to show no subtitles.")
            self.plexHelper.unset_video_subtitles_for_user(video=next_episode, user=session.user)
            return
                
        self.manually_check_video_subtitles(next_episode.key)
        next_episode.reload()
        self.plexHelper.select_video_subtitles_for_user(video=next_episode, user=session.user, subtitle_to_match=subtitle_stream)


    def manually_check_video_subtitles(self, video_key):
        """Manually check video for missing subtitles, and try to download missing subs.
        """

        video = self.plexHelper.get_video_item(video_key)
        if video is None:
            log.info(f"Video with key {video_key} could not be retrieved.")
            return 
        self.handle_downloading_video_subtitles(video)

    def handle_downloading_video_subtitles(self, video):
        missingVideos = self.get_videos_missing_subtitles([video])
        log.info("Found " + str(len(missingVideos)) + " videos missing subtitles")
        log.info([f'{video.title}, {video.key}' for video in missingVideos])
        if len(missingVideos) > 0:
            subtitles = self.download_subtitles_for_videos(missingVideos)

            if self.subtitle_destination == "metadata":
                self.upload_subtitles_to_metadata(missingVideos, subtitles)
            else:
                self.sub.save_subtitles(subtitles)
        else:
            log.info("No subtitles to download, doing nothing!")
        
    def get_videos_missing_subtitles(self,videos):
        """Search the given list of videos for ones that don't already have subtitles.
        For videos of type 'season' or 'show', this will search through all of the episodes
        as well.
        :param list videos: list of plexapi.video.Video objects.
        :return: list of Video objects that don't have any subtitles.
        """

        vidsMissingSubs = []
        for v in videos:
            if v.type == 'movie' or v.type == 'episode':
                if self.is_video_missing_subtitles(v):
                    vidsMissingSubs.append(v)
                
            elif v.type == 'season' or v.type == 'show':
                eps = v.episodes()
                for e in eps:
                    e.reload()
                    if self.is_video_missing_subtitles(e):
                        vidsMissingSubs.append(e)

        return vidsMissingSubs

    def is_video_missing_subtitles(self, video):
        """Checks the given video to see if it's missing subtitles for any of the languages defined in config['languages'].
        :param video: plexapi.video.Video object
        :return: boolean, False if the video has subtitles for every requested language, True otherwise
        """

        missingSubtitles = self.get_missing_subtitle_languages(video)
        return len(missingSubtitles) > 0
    
    def get_missing_subtitle_languages(self, video):
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

    def download_subtitles_for_videos(self, videos):
        """Attempts to download subtitles for the given list of videos.
        :param list videos: list of plexapi.video.Video objects.
        :return: dict[subliminal.video.Video, list[subliminal.subtitle.Subtitle]]
        """

        log.info(f"Downloading subtitles for {len(videos)} videos:")
        log.info([video.title for video in videos])
        missing_languages = [self.get_missing_subtitle_languages(video) for video in videos]
        subtitles = self.sub.search_videos(videos, missing_languages)
        return subtitles

    def upload_subtitles_to_metadata(self, plexVideos, subtitleDict):
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
                            
    def check_webhook_registration(self):
        return self.plexHelper.check_webhook_registration()
    
    def add_webhook_to_plex(self):
        return self.plexHelper.add_webhook_to_plex()
        
    def save_webhook_event(self, event, dir):
        import json
        import time
        
        webhook_filename = f'event_{int(time.time())}_{event.event}.json'
        filepath = os.path.join(dir, webhook_filename)
        with open(filepath, 'w') as fp:
            log.debug(f'Saving webhook event to {filepath}')
            json.dump(event._data, fp, indent=4)

