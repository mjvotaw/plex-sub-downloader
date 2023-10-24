import os
from re import sub

from babelfish import *
import subliminal
from subliminal import region
from subliminal.core import ProviderPool
from subliminal.providers.opensubtitles import ( OpenSubtitlesVipProvider, OpenSubtitlesVipSubtitle)
from subliminal.video import (Video as SubVideo, Episode, Movie)
from subliminal.subtitle import Subtitle

from plexapi import media
from plexapi.media import (Media, MediaPart)
from plexapi.video import Video as PlexVideo

from plex_sub_downloader.logger import Logger
log = Logger.getInstance().getLogger()

class SubliminalHelper:

    def __init__(self, languages=['eng'], providers=None, provider_configs=None):

        self.region = region.configure('dogpile.cache.dbm', arguments={'filename': 'subliminalCache.dbm'})
        self.languages = set([subliminal.core.Language(lang) for lang in languages])

        self.providers = providers
        if providers is None and provider_configs is not None:
            self.providers = [provider for provider in provider_configs]

        self.provider_configs = provider_configs

        log.debug("Setting up Subliminal with configs:")
        log.debug("languages:")
        log.debug(self.languages)
        log.debug("providers:")
        log.debug(self.providers)
        log.debug("provider_configs:")
        log.debug(self.provider_configs)

    def search_video(self, video):
        """Searches subtitles for the given video.
        :param video: plexapi.video.Video object
        :return: list[subliminal.subtitle.Subtitle]
        """
        subVideo = self.build_subliminal_video(video)
        return self.search_sub_video(subVideo)

    def search_videos(self, videos):
        """Searches subtitles for multiple videos at once.
        :param videos: list of plexapi.video.Video objects.
        :return: dict[subliminal.video.Video, list[subliminal.subtitle.Subtitle]]
        """
        subVideos = [self.build_subliminal_video(v) for v in videos]
        subtitles = subliminal.download_best_subtitles(subVideos, languages=self.languages, providers=self.providers, provider_configs=self.provider_configs)
        log.debug(subtitles)
        return subtitles

    def search_sub_video(self, sub_video):
        """Searches subtitles for the given video.
        :param video: subliminal.video.Video object.
        :return: list[subliminal.subtitle.Subtitle]
        """
        subtitles = subliminal.download_best_subtitles([sub_video], languages=self.languages, providers=self.providers, provider_configs=self.provider_configs)
        log.debug(subtitles)
        return subtitles[sub_video]

    
    def save_subtitle(self, video, subtitle, destination=None):
        """Saves the given subtitle (or subtitles) for the given video.
        :param video: Either plexapi.video.Video or subliminal.video.Video object.
        :param subtitle: Either a single subliminal.subtitle.Subtitle object, or list[subliminal.subtitle.Subtitle]
        :param destination: (Optional) An optional destination for the subtitle files. If None, the subtitles will be
        saved alongside the video file.
        :return: list[string] A list of filepaths of the successfully saved subtitles.
        """
        videoFilepath = destination
        subVideo = video if isinstance(video, SubVideo) else self.build_subliminal_video(video)
        if destination is None:
            videoFilepath = os.path.dirname(subVideo.name)

        log.debug("Saving subtitle file to " + videoFilepath)
        subtitles = subtitle if isinstance(subtitle, list) else [subtitle]
        savedFilepaths = []
        savedSubtitles = subliminal.core.save_subtitles(subVideo, subtitles, directory=videoFilepath)

        for subtitle in savedSubtitles:
            defaultSubtitlePath = subtitle.get_path(video, single=False)
            savedSubtitlePath = os.path.join(videoFilepath, os.path.split(defaultSubtitlePath)[1])
            savedFilepaths.append(savedSubtitlePath)
        return savedFilepaths

    def save_subtitles(self, subtitles):
        """Saves subtitles for mutliple videos.
        :param subtitles: dict[subliminal.video.Video, list[Subliminal.subtitle.Subtitle]]
        :return: list[string] A list of filepaths of the successfully saved subtitles.
        """
        savedFilepaths = []
        for video, subs in subtitles.items():
            log.info(f'Found {len(subs)} subtitles for video \'{video.name}\'')
            saved = self.save_subtitle(video, subs)
            savedFilepaths = savedFilepaths + saved
        
        return savedFilepaths

    def build_subliminal_videos(self, videos):
        """Converts the given plexapi.video.Video objects into subliminal.video.Video objects.
        :param videos: a list of plexapi.video.Video objects.
        :return: dict[plexapi.video.Video, subliminal.video.Video]
        """
        subVideos = {}
        for video in videos:
            subVideo = self.build_subliminal_video(video)
            subVideos[video] = subVideo

        return subVideos

    def build_subliminal_video(self, video):
        """Converts the given plexapi.video.Video object into subliminal.video.Video
        :param video: plexapi.video.Video object
        :return: subliminal.video.Video object
        """
        videoMedia = video.media[0]
        videoPart = videoMedia.parts[0]

        fileName = videoPart.file
        imdb_id = None

        for guid in video.guids:
            guid_id_parts = guid.id.split("://")
            if len(guid_id_parts) == 2 and guid_id_parts[0] ==  "imdb":
                imdb_id = int(guid_id_parts[1].replace("tt",""))
                break

        if video.type == "episode":

            seriesTitle = video.grandparentTitle
            season = int(video.parentTitle.replace("Season ", ""))
            episodeTitle = video.title
            episodeNumber = int(video.index)
            subEpisode = Episode(name=fileName, series=seriesTitle, season=season, episodes=episodeNumber, title=episodeTitle)
            return subEpisode
        else:
            subMovie = Movie(name=fileName, title=video.title, year=video.year, imdb_id=[imdb_id])
            return subMovie
        
