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
    log.debug(data)
    log.debug("\n\n\n")

    event = PlexWebhookEvent(data)
    psd.handleWebhookEvent(event)
    return Response(status=200)


def main():

    usage = ("{FILE} "
             "--config <config_file.json> "
             "<command> (one of: configtest, start-webhook)"
             ).format(FILE=__file__)

    description = 'Download subtitles for recently added Plex media'
    parser = argparse.ArgumentParser(usage=usage, description=description)
    parser.add_argument("-v", "--version", action="version", version=f'plex_sub_downloader version {version("plex_sub_downloader")}', help="Prints version info and exits")
    parser.add_argument("-c", "--config", help="Config File", default="config.json")
    parser.add_argument("-d", "--debug", help="Set log level to Debug", action='store_true', required=False)
    parser.add_argument("command", 
    nargs="+",
    choices=["configtest", "start-webhook"],
    help="Command to perform"
    )

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
    log.debug("Config params:")
    log.debug(config)

    if "configtest" in args.command:
        log.info(f'Testing config file \'{args.config}\'')
        schema = loadConfig(os.path.join(os.path.abspath(os.path.dirname(__file__)), "config.schema.json"))
        jsonschema.validate(instance=config, schema=schema)
        log.info('config file is valid.')
        return

    if psd.configure(config) == False:
        log.error("An error occurred during configuration.")
        return
    
    if "start-webhook" in args.command:
        log.info("plex-sub-downloader starting up")
        checkPlexConfiguration()
        runFlask(config)
        log.info("plex-sub-downloader shutting down")

    

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
