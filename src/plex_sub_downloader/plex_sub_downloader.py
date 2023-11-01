import os
import argparse
import json
import jsonschema
import sys
from waitress import serve
from flask import Flask, request, Response
import logging
from .PlexWebhookEvent import PlexWebhookEvent
from .PlexSubDownloader import PlexSubDownloader
from importlib.metadata import version

log = logging.getLogger('plex-sub-downloader')
psd = PlexSubDownloader() 
APP = Flask(__name__)

@APP.route('/webhook', methods=['POST'])
def respond():
    """
    Handle POST request sent from Plex server
    """
    data = json.loads(request.form.get('payload'))
    
    event = PlexWebhookEvent(data)
    psd.handleWebhookEvent(event)
    return Response(status=200)


def main():

    usage = ("{FILE} "
             "--config <config_file.json> "
             "<command>"
             ).format(FILE=__file__)

    description = 'Download subtitles for recently added Plex media'
    parser = argparse.ArgumentParser(usage=usage, description=description)
    parser.add_argument("-v", "--version", action="version", version=f'plex_sub_downloader version {version("plex_sub_downloader")}', help="Prints version info and exits")
    parser.add_argument("-c", "--config", help="Config File", default="config.json")
    parser.add_argument("-d", "--debug", help="Set log level to Debug", action='store_true', required=False)

    subparsers = parser.add_subparsers(title='commands', dest='command')
    subparsers.add_parser('configtest', description='Validates the config file provided by the --config option.')
    subparsers.add_parser('start-webhook', description='Runs the Plex webhook and listens for newly added videos.')

    checkvideo_parser = subparsers.add_parser('check-video', description='Manually check the given video key for mising subtitles.')
    checkvideo_parser.add_argument('video_key', help="The metadata key of a Movie, Episode, Season, or Show (example \"/library/metadata/42069\")")
    
    parser.set_defaults(debug=False)

    args = parser.parse_args()
    setupLogging()
    config = loadConfig(args.config)

    if args.debug:
        log.setLevel(level=logging.DEBUG)
    else:
        log.setLevel(level=config.get('log_level',logging.INFO))

    log.debug("cmdline arguments:")
    log.debug(args)

    if args.command is None:
        parser.print_help()
        return
    
    if args.command == "configtest":
        log.info(f'Testing config file \'{args.config}\'')
        schema = loadConfig(os.path.join(os.path.abspath(os.path.dirname(__file__)), "config.schema.json"))
        jsonschema.validate(instance=config, schema=schema)
        log.info('config file is valid.')
        return

    if psd.configure(config) == False:
        log.error("An error occurred during configuration.")
        return
    
    if args.command == "start-webhook":
        log.info("plex-sub-downloader starting up")
        checkPlexConfiguration()
        runFlask(config)
        log.info("plex-sub-downloader shutting down")

    if args.command == "check-video":
        key = args.video_key
        psd.manuallyCheckVideoSubtitles(key)
    

def loadConfig(filepath):

    with open(filepath, 'r') as fp:
        config = json.load(fp)
        return config  

def checkPlexConfiguration():
    if psd.checkWebhookRegistration() == False:
        psd.addWebhookToPlex()

def runFlask(config):
    host = config.get('webhook_host', None)
    port = config.get('webhook_port', None)
    serve(APP, host=host, port=port)

def setupLogging():
    log_format = '%(asctime)s:%(module)s:%(levelname)s - %(message)s'
    date_format = "%Y-%m-%d %H:%M:%S"
    handler = logging.StreamHandler()
    formatter = logging.Formatter(log_format, date_format)
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.propagate = False

if __name__ == '__main__':
    main()
