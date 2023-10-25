class PlexWebhookEvent(object):
    """
    Object representation of a plex user event.
    """

    def __init__(self, data):
        self.event = data['event']
        self.Account = None
        self.Server = None
        self.Player = None
        self.Metadata = None

        if "Account" in data:
            self.Account = PlexAccount(data["Account"])
        
        if "Player" in data:
            self.Player = PlexPlayer(data["Player"])

        if "Server" in data:
            self.Server = PlexServer(data["Server"])
        
        if "Metadata" in data:
            self.Metadata = PlexMetadata(data["Metadata"])
    
    def __str__(self):
        return str(self.__dict__)


class PlexAccount(object):

    def __init__(self, data):
        self.id = data.get('id', None)
        self.thumb = data.get('thumb', None)
        self.title = data.get('title', None)


class PlexPlayer(object):

    def __init__(self, data):
        self.local = data.get('local', None)
        self.publicAddress = data.get('publicAddress', None)
        self.title = data.get('title', None)
        self.uuid = data.get('uuid', None)
    
    def __str__(self):
        return str(self.__dict__)


class PlexServer(object):

    def __init__(self, data):
        self.title = data.get('title', None)
        self.uuid = data.get('uuid', None)
    
    def __str__(self):
        return str(self.__dict__)


class PlexMetadata(object):

    def __init__(self, data):
        self.librarySectionType = data.get('librarySectionType', None)
        self.ratingKey = data.get('ratingKey', None)
        self.key = data.get('key', None)
        self.guid = data.get('guid', None)
        self.studio = data.get('studio', None)
        self.type = data.get('type', None)
        self.title = data.get('title', None)
        self.librarySectionTitle = data.get('librarySectionTitle', None)
        self.librarySectionID = data.get('librarySectionID', None)
        self.librarySectionKey = data.get('librarySectionKey', None)
        self.contentRating = data.get('contentRating', None)
        self.summary = data.get('summary', None)
        self.audienceRating = data.get('audienceRating', None)
        self.year = data.get('year', None)
        self.tagline = data.get('tagline', None)
        self.thumb = data.get('thumb', None)
        self.art = data.get('art', None)
        self.duration = data.get('duration', None)
        self.originallyAvailableAt = data.get('originallyAvailableAt', None)
        self.addedAt = data.get('addedAt', None)
        self.updatedAt = data.get('updatedAt', None)
        self.audienceRatingImage = data.get('audienceRatingImage', None)
        self.primaryExtraKey = data.get('primaryExtraKey', None)

        self.Genre = PlexProp.createProp(data.get('Genre', []))
        self.Director = PlexProp.createProp(data.get('Director', []))
        self.Writer = PlexProp.createProp(data.get('Writer', []))
        self.Producer = PlexProp.createProp(data.get('Producer', []))
        self.Country = PlexProp.createProp(data.get('Country', []))
        self.Rating = PlexProp.createProp(data.get('Rating', []))
        self.Role = PlexProp.createProp(data.get('Role', []))

        self.Guid = PlexGuid.createGuids(data.get('Guid', []))


    def __str__(self):
        return str(self.__dict__)


class PlexGuid(object):

    def __init__(self, id):

        idParts = id.split(":/")
        self.type = None
        self.id = None
        if len(idParts) == 2:
            self.type = idParts[0]
            self.id = idParts[1]
    
    def __str__(self):
        return str(self.__dict__)

    @staticmethod
    def createGuids(data):

        guids = []
        for d in data:
            guids.append(PlexGuid(d["id"]))
        return guids


class PlexProp(object):

    def __init__(self, data):
        self.id = data.get('id', None)
        self.filter = data.get('filter', None)
        self.tag = data.get('tag', None)
        self.count = data.get('count', None)
        self.role = data.get('role', None)
        self.thumb = data.get('thumb', None)

    def __str__(self):
        return self.__dict__

    @staticmethod
    def createProp(arr):

        people = []
        for d in arr:
            people.append(PlexProp(d))
        
        return people
        




