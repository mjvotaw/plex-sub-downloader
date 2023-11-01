import os
from re import sub
from pathlib import Path
from operator import itemgetter

from babelfish import *
import subliminal
from subliminal import region
from subliminal.score import compute_score
from subliminal.core import ProviderPool
from subliminal.providers.opensubtitles import ( OpenSubtitlesVipProvider, OpenSubtitlesVipSubtitle)
from subliminal.video import (Video as SubVideo, Episode, Movie)
from subliminal.subtitle import Subtitle
from subliminal.utils import hash_napiprojekt, hash_opensubtitles, hash_shooter, hash_thesubdb

from plexapi import media
from plexapi.media import (Media, MediaPart)
from plexapi.video import Video as PlexVideo
import logging
import itertools

log = logging.getLogger('plex-sub-downloader')

class SubliminalHelper:

    def __init__(self, providers=None, provider_configs=None, format_priority=None):

        if region.is_configured == False:
            region.configure('dogpile.cache.dbm', arguments={'filename': 'subliminalCache.dbm'})
        self.format_priority = format_priority
        self.providers = providers
        if providers is None and provider_configs is not None:
            self.providers = [provider for provider in provider_configs]

        self.provider_configs = provider_configs

        log.debug("Setting up Subliminal with configs:")
        log.debug("providers:")
        log.debug(self.providers)

        self.hash_functions = {
            'opensubtitles': hash_opensubtitles,
            'shooter': hash_shooter,
            'thesubdb': hash_thesubdb,
            'napiprojekt': hash_napiprojekt,
        }

    def search_video(self, video, languages):
        """Searches subtitles for the given video.
        :param video: plexapi.video.Video object
        :return: list[subliminal.subtitle.Subtitle]
        """
        subVideo = self.build_subliminal_video(video)
        return self._search_videos(subVideo, languages)

    def search_videos(self, videos, languages):
        """Searches subtitles for multiple videos at once.
        :param videos: list of plexapi.video.Video objects.
        :return: dict[subliminal.video.Video, list[subliminal.subtitle.Subtitle]]
        """
        subVideos = [self.build_subliminal_video(v) for v in videos]
        return self._search_videos(subVideos, languages)
    
    def _search_videos(self, videos, languages):
        """Actually handles searching for subtitles.
        :param videos: list[subliminal.video.Video]
        :param languages: list[list[str]] A list of languages to find for each video.
        :return: dict[subliminal.video.Video, list[subliminal.subtitle.Subtitle]]
        """
        sub_languages = [[subliminal.core.Language(l) for l in vid_langs] for vid_langs in languages]
        languages_list = set(itertools.chain.from_iterable(sub_languages))
        subtitles = subliminal.list_subtitles(videos, languages=languages_list, providers=self.providers, provider_configs=self.provider_configs)
        
        best_subtitles = {}

        for i in range(0, len(videos)):
            video = videos[i]
            video_languages = sub_languages[i]
            subs = subtitles[video]
            best_subs = self.select_best_subtitles(video, subs, video_languages)
            if best_subs is not None:
                best_subtitles[video] = best_subs
        
        log.debug(best_subtitles)
        return best_subtitles

    def select_best_subtitles(self, video, subtitles, languages):
        """Selects the 'best' subtitles for the given video based on a combination of factors, including subliminal.score.compute_score, and subtitle format priority. 
        Returns 1 subtitle for each language (if any were found).
        :param video: subliminal.video.Video object
        :param subtitles: list[subliminal.subtitle.Subtitle]
        :param languages: list[subliminal.core.Language]
        :return: list[subliminal.subtitle.Subtitle]
        """
        subtitles = self.filter_subtitles(video, subtitles)

        # Build a decorated list of subtitles that includes their "score" and their format priority.
        # Sort the list by format priority from highest to lowest, and then score from highest to lowest.
        decorated_subtitles = [(compute_score(subtitle, video), self._get_subtitle_format_priority(subtitle, video), subtitle) for subtitle in subtitles]
        decorated_subtitles.sort(key=itemgetter(1), reverse=True)
        decorated_subtitles.sort(key=itemgetter(0), reverse=True)
        subtitles = [subtitle for score, fmt_priority, subtitle in decorated_subtitles]

        # Find the first subtitle for each language
        selected_subtitles = [] 
        for lang in languages:
            for sub in subtitles:
                if sub.language == lang:
                    selected_subtitles.append(sub)
                    break

        return selected_subtitles

    def filter_subtitles(self, video, subtitles):
        """Filters the list of subtitles based on config preferences.
        :param video: subliminal.video.Video object
        :param subtitles: list[subliminal.subtitle.Subtitle]
        :return: list[subliminal.subtitle.Subtitle]
        """

        filtered_subtitles = subtitles.copy()
        
        if self.format_priority is not None:
            filtered_subtitles = [s for s in filtered_subtitles if self._get_subtitle_format(s, video) in self.format_priority]
        
        return filtered_subtitles

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

        filepath = videoPart.file
        imdb_id = None

        for guid in video.guids:
            guid_id_parts = guid.id.split("://")
            if len(guid_id_parts) == 2 and guid_id_parts[0] ==  "imdb":
                imdb_id = int(guid_id_parts[1].replace("tt",""))
                break

        if video.type == "episode":

            seriesTitle = video.grandparentTitle
            season = int(video.seasonNumber)
            episodeTitle = video.title
            episodeNumber = int(video.episodeNumber)
            subVideo = Episode(name=filepath, series=seriesTitle, season=season, episodes=episodeNumber, title=episodeTitle)
        else:
            subVideo = Movie(name=filepath, title=video.title, year=video.year, imdb_id=[imdb_id])

        if videoPart.size > 10485760:
            subVideo = self.set_video_hashes(subVideo)

        return subVideo
    
    def set_video_hashes(self, subVideo):
        """Computes hashes as needed for any subtitle providers being used, and returns the subVideo object.
            If the file cannot be accessed (either due to permissions, or if the file is only available remotely),
            nothing will be done.
            :param subVideo: subliminal.video.Video object
            :return: subliminal.video.Video object
        """
        
        if os.path.exists(subVideo.name) == False:
            return subVideo
        
        for provider in self.providers:
                if provider in self.hash_functions.keys():
                    subVideo.hashes[provider] = self.hash_functions[provider](subVideo.name)
        return subVideo
        
    def _get_subtitle_format(self, subtitle, video):
        """Returns the file extension for the given subtitle, with the '.' removed."""

        return Path(subtitle.get_path(video)).suffix.replace(".", "")
    
    def _get_subtitle_format_priority(self, subtitle, video):
        """Returns the 'priority' of the format for the given subtitle, based on the `subtitle_preferences` config.
        A higher value is considered higher priority. A value of -1 means that the given format was not found in `subtitle_preferences`.
        If `subtitle_preferences` is None, then this will return 0 for all format. 
        """
        if self.format_priority is None:
            return 0

        fmt = self._get_subtitle_format(subtitle, video)
        if fmt not in self.format_priority:
            return -1
        return len(self.format_priority) - self.format_priority.index(fmt)