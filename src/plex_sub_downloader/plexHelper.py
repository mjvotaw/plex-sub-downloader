import os
import logging
import plexapi
from plexapi.server import PlexServer
from plexapi.video import Video, Episode, EpisodeSession
from plexapi.library import LibrarySection
from plexapi.media import SubtitleStream
import socket

log = logging.getLogger('plex-sub-downloader')

class PlexHelper:

    def __init__(self, baseurl, token, host="0.0.0.0", port=None):
        self.plexServer = PlexServer(baseurl=baseurl, token=token)
        self.host = host
        self.port = port

    def get_video_item_from_event(self, event):
         # if Metadata.type == "show", then the metadata key looks like
        # `/library/metadata/45533/children`, which doesn't return what we actually want
        # when we call fetchItem
        key = event.Metadata.key
        return self.get_video_item(key)

    def get_video_item(self, key):
        key = key.replace("/children", "")
        try:
            video = self.plexServer.fetchItem(ekey=key)
            video.reload()
            return video
        except Exception as e:
            log.error(f'Error while trying to retrieve video with key {key}')
            log.error(e)
            return None
        
    def get_next_episode(self, key):
        """A convenience function that attempts to find the next episode for the given video key.
            :param str key:
            :return plexapi.video.Episode | None:
        """
        video = self.get_video_item(key)
        if video is None or type(video) is not Episode:
            return None
        
        log.debug(f"Searching for next episode for video {video.key}")
        show = video.show()

        nextEpisode = None

        #show.episode throws an exception if it can't find the video, because plexapi tries to parse a non-existent response
        try:
            nextEpisode = show.episode(season=int(video.seasonNumber), episode=int(video.episodeNumber) + 1)
        except:
            log.debug(f"Next episode in season not found, checking for first episode of next season")
            try:
                nextEpisode = show.episode(season=int(video.seasonNumber) + 1, episode = 1)
            except:
                log.debug(f"First episode of next season not found. This must be the last episode of the show(?)")
                return None
        finally:
            if nextEpisode is not None:
                nextEpisode.reload()
                log.debug(f"Found next episode for video {video.key}: {nextEpisode.key}")
            return nextEpisode

    
    def get_session_for_play_event(self, event):
        """Searches for a currently active session matching the given event.
        :param PlexWebhookEvent event:
        :return plexapi.video.PlexSession | None:
        """
        log.debug(f"Searching for active session for event {event.Metadata.guid}")
        sessions = self.plexServer.sessions()
        for session in sessions:
            if session.user.id == event.Account.id and session.guid == event.Metadata.guid:
                log.debug(f"Found active session matching event {event.Metadata.guid}")
                return session
        
        return None

    def get_selected_subtitles_for_play_session(self, session):
        """Finds the selected SubtitleStream object (if any) for the given session.
            :param plexapi.video.PlexSession session:
            :return plexapi.media.SubtitleStream | None:
        """

        log.debug(f"Searching for selected SubtitleStream for session {session.session.id}")
        for media in session.media:
            if media.selected != True:
                continue
            for part in media.parts:
                if part.selected != True:
                    continue
                for stream in part.streams:
                    if type(stream) is SubtitleStream and stream.selected == True:
                        log.debug(f"Found selected SubtitleStream {stream.id} for session {session.session.id}")
                        return stream
        return None

    def select_video_subtitles_for_user(self, video, user, subtitle_to_match):
        """A convenience function to find and set subtitles for the given video and user that best match the given SubtitleStream.
        :param plexapi.video.Video video:
        :param plexapi.myplex.MyPlexAccount user:
        :param plexapi.media.SubtitleStream subtitle_to_match:
        """

        matching_subtitles = self.find_matching_subtitles_for_video(subtitle_to_match=subtitle_to_match, video=video)

        ps = self.switch_user(user)
        for video_part_id, matching_subtitle in matching_subtitles.items():
            log.debug(f"Setting subtitles {matching_subtitle.id} for user {user.id} on MediaPart {video_part_id}")
            query_url = f"/library/parts/{video_part_id}?subtitleStreamID={matching_subtitle.id}"
            ps.query(query_url, method=ps._session.put)

    def unset_video_subtitles_for_user(self, video, user):
        """A convenience function to unset the subtitle selections for the given video and given user.
        :param plexapi.media.Video video:
        :param plexapi.myplex.MyPlexAccount user:
        """

        ps = self.switch_user(user)
        for media in video.media:
            for part in media.parts:
                log.debug(f"Unsetting subtitle selection for user {user.title} on MediaPart {part.id}")
                query_url = f"/library/parts/{part.id}?subtitleStreamID=0"
                ps.query(query_url, method=ps._session.put)

    def find_matching_subtitles_for_video(self, subtitle_to_match, video):
        """Find subtitles on each MediaPart of the given video that best matches the given subtitle from a different video.
            Returns a dictionary of MediaPart id's and matching SubtitleStream. If no matching SubtitleStream is found for a certain MediaPart,
            then it will be excluded from the returned dictionary.
            :param plex.media.SubtitleSteam subtitle_to_match:
            :param plex.video.Video video:
            :return dict[str, plex.media.SubtitleStream]
        """
        log.debug(f"Searching subtitles for video {video.key} that match subtitle {subtitle_to_match.id}")

        matching_subtitles = {}
        for media in video.media:
            for part in media.parts:
                matching_subtitle = None
                matching_subtitle_score = 0
                for stream in part.streams:
                    if type(stream) is not SubtitleStream:
                        continue

                    if stream.languageCode != subtitle_to_match.languageCode:
                        continue

                    score = self.score_subtitle_match(stream, subtitle_to_match)
                    log.debug(f"Calculated subtitle match score of {score} for SubtitleStream {stream.id}")
                    if score > matching_subtitle_score:
                        matching_subtitle_score = score
                        matching_subtitle = stream
                
                if matching_subtitle is not None:
                    log.debug(f"Selected matching subtitle {matching_subtitle.id} for MediaPart {part.id} with a score of {matching_subtitle_score} against subtitle {subtitle_to_match.id}")
                    matching_subtitles[part.id] = matching_subtitle
                else:
                    log.debug(f"No matching subtitles found for MediaPart {part.id} against subtitle {subtitle_to_match.id}")
        
        return matching_subtitles
    
    def score_subtitle_match(self, subtitle, subtitle_to_match):
        """Calculates a 'score' of how well two SubtitleStreams from different videos match.
        The calculation is weighted towards favoring the same language (since that's pretty important) and format.
        :param plex.media.SubtitleSteam subtitle:
        :param plex.media.SubtitleSteam subtitle_to_match:
        :return int:
        """
        score = 0
        score += 5 if subtitle.language == subtitle_to_match.language else 0
        score += 2 if subtitle.languageCode == subtitle_to_match.languageCode else 0
        score += 2 if subtitle.languageTag == subtitle_to_match.languageTag else 0
        score += 2 if subtitle.format == subtitle_to_match.format else 0
        score += 1 if subtitle.displayTitle == subtitle_to_match.displayTitle else 0
        score += 1 if subtitle.providerTitle == subtitle_to_match.providerTitle else 0
        score += 1 if subtitle.decision == subtitle_to_match.decision else 0
        score += 1 if subtitle.location == subtitle_to_match.location else 0

        return score
    
    def switch_user(self, user):
        """Wrapper function for calling PlexServer.switchUser(). 
        If user is the admin account, then PlexServer.switchUser() will raise an exception, 
        so the default plexServer object will be returned.
        :param plexapi.myplex.MyPlexAccount user:
        :return plexapi.server.PlexServer:
        """

        admin = self.plexServer.myPlexAccount()
        if user.id == admin.id:
            return self.plexServer
        else: 
            return self.plexServer.switchUser(user.title)

    def check_library_permissions(self, sectionId=None):
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

    # Methods for checking webhook registration

    def check_webhook_registration(self):
        webhookUrl = self.get_webhook_url()
        log.info(f'Checking if webhook url {webhookUrl} has been added to Plex...')

        plexAccount = self.plexServer.myPlexAccount()
        webhooks = plexAccount.webhooks()

        if webhookUrl in webhooks:
            log.info(f'webhook url {webhookUrl} has been added to Plex')
            return True
        else:
            log.info(f'webhook url {webhookUrl} has NOT been added to Plex')
            return False
    
    def add_webhook_to_plex(self):
        webhookUrl = self.get_webhook_url()
        plexAccount = self.plexServer.myPlexAccount()
        log.info(f'Attempting to add webhook url {webhookUrl} to Plex...')
        webhooks = plexAccount.addWebhook(webhookUrl)
        if webhookUrl in webhooks:
            log.info('Webhook url successfully added!')
            return True
        else:
            log.error(f'Could not add the webhook url {webhookUrl} to Plex. You may need to manually add this through the web dashboard.')
            return False
        

    def get_webhook_url(self):
        host = self.get_external_host()
        port = self.port
        if port is not None:
            port = f":{port}"

        webhookUrl = f"http://{host}{port}/webhook"
        return webhookUrl
    
    def get_external_host(self):
        host = self.host
        
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