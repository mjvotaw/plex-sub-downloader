import logging
import plexapi
from plexapi.server import PlexServer
from plexapi.video import Video, EpisodeSession
from plexapi.library import LibrarySection
from plexapi.media import SubtitleStream
import socket

log = logging.getLogger('plex-sub-downloader')

class PlexHelper:

    def __init__(self, baseurl, token, host="0.0.0.0", port=None):
        self.plexServer = PlexServer(baseurl=baseurl, token=token)
        self.host = host
        self.port = port

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
    
    def getSessionForPlayEvent(self, event):
        sessions = self.plexServer.sessions()
        for session in sessions:
            if session.user.id == event.Account["id"] and session.guid == event.Metadata["guid"]:
                return session
        
        return None

    def getSubtitlesForSession(self, session):
        
        for media in session.media:
            for part in media.parts:
                for stream in part.streams:
                    if type(stream) is SubtitleStream:
                        return stream
        return None
    

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

    # Methods for checking webhook registration

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
        port = self.port
        if port is not None:
            port = f":{port}"

        webhookUrl = f"http://{host}{port}/webhook"
        return webhookUrl
    
    def getExternalHost(self):
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